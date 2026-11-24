"""Bot command handlers and the Telegram application entry point."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
from collections.abc import Callable
from contextlib import redirect_stdout
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any

from aiogram import Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import kino
from movie_bluff_ai_bot import state, telegram

PickFunction = Callable[[Any, str, str, list[dict[str, Any]]], tuple[str, list[str | int]]]
DEFAULT_MAX_CLARIFY_TURNS = 1


def _max_clarify_turns() -> int:
    raw = os.environ.get("MAX_CLARIFY_TURNS", str(DEFAULT_MAX_CLARIFY_TURNS)).strip()
    try:
        turns = int(raw)
    except ValueError as error:
        raise ValueError("MAX_CLARIFY_TURNS must be a non-negative integer") from error
    if turns < 0:
        raise ValueError("MAX_CLARIFY_TURNS must be a non-negative integer")
    return turns


def configure_logging() -> None:
    for name in ("httpx", "httpcore", "aiogram"):
        logging.getLogger(name).setLevel(logging.WARNING)


class BotHandlers:
    """Register and implement the first-pass command and selection handlers."""

    def __init__(
        self,
        *,
        client: Any,
        model: str,
        films: list[dict[str, Any]],
        state_path: str | Path | None = None,
        picker: PickFunction | None = None,
    ) -> None:
        self.client = client
        self.model = model
        self.films = films
        self.state_path = state_path
        self.picker = kino.pick if picker is None else picker

    def register(self, router: Router) -> None:
        router.message.register(self.start, Command("start"))
        router.message.register(self.help, Command("help"))
        router.message.register(self.new, Command("new"))
        router.message.register(self.more, Command("more"))
        router.callback_query.register(self.callback)
        router.message.register(self.unknown, F.text.startswith("/"))
        router.message.register(self.text, F.text & ~F.text.startswith("/"))

    async def _send(
        self,
        bot: Any,
        chat_id: int,
        text: str,
        *,
        reply_markup: Any = None,
    ) -> None:
        await telegram.send_text(bot, chat_id, text, reply_markup=reply_markup)

    async def _reply(self, message: Message, text: str, *, reply_markup: Any = None) -> None:
        await self._send(message.bot, message.chat.id, text, reply_markup=reply_markup)

    def _load_state(self, chat_id: int) -> state.BotState:
        return state.load_chat_state(chat_id, self.state_path)

    def _save_state(self, chat_id: int, value: state.BotState) -> None:
        value["updated_at"] = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        try:
            state.save_chat_state(chat_id, value, self.state_path)
        except OSError:
            print("warning: cannot persist bot state", file=sys.stderr)

    async def start(self, message: Message) -> None:
        keyboard = InlineKeyboardBuilder()
        for genre in kino.GENRES:
            keyboard.button(text=genre.title(), callback_data=f"genre:{genre}")
        keyboard.adjust(2)
        await self._reply(
            message,
            "Welcome to Movie Buff. Choose a genre or send a movie request.",
            reply_markup=keyboard.as_markup(),
        )

    async def help(self, message: Message) -> None:
        await self._reply(
            message,
            "Send a movie request in English, Russian, or Kazakh. "
            "Use /start to choose a genre, /more for another recommendation, "
            "or /new to start over.",
        )

    async def new(self, message: Message) -> None:
        self._save_state(message.chat.id, state.new_state())
        await self._reply(message, "Started a new session. Send a movie request when ready.")

    async def more(self, message: Message) -> None:
        current = self._load_state(message.chat.id)
        query = current["last_query"]
        if not query:
            await self._reply(message, "Send a movie request first, then use /more.")
            return
        await self._select(message, query)

    async def unknown(self, message: Message) -> None:
        await self.help(message)

    async def text(self, message: Message) -> None:
        query = message.text or ""
        if query.strip():
            current = self._load_state(message.chat.id)
            if current["pending_clarify"] is not None:
                previous = current["last_query"] or ""
                merged_query = f"{previous}\n{query}".strip()
                await self._select_target(
                    message.bot,
                    message.chat.id,
                    merged_query,
                    current=current,
                    clarification_answer=True,
                )
            else:
                await self._select_target(
                    message.bot,
                    message.chat.id,
                    query,
                    current=current,
                )

    async def callback(self, callback: CallbackQuery) -> None:
        await callback.answer()
        data = callback.data or ""
        message = callback.message
        if not telegram.callback_data_allowed(data) or message is None:
            return
        _prefix, _separator, genre = data.partition(":")
        await self._select_target(callback.bot, message.chat.id, f"Recommend a {genre} film.")

    async def _select(self, message: Message, query: str) -> None:
        await self._select_target(message.bot, message.chat.id, query)

    async def _select_target(
        self,
        bot: Any,
        chat_id: int,
        query: str,
        *,
        current: state.BotState | None = None,
        clarification_answer: bool = False,
    ) -> None:
        current = self._load_state(chat_id) if current is None else current
        lowered = query.casefold()
        exclusion_cues = (
            "already watched",
            "don't want",
            "do not want",
            "except",
            "without",
            "не хочу",
            "не смотрел",
            "уже смотрел",
            "кроме",
            "без",
        )
        if any(cue in lowered for cue in exclusion_cues):
            excluded_ids = {str(value) for value in current["excluded_ids"]}
            for film in self.films:
                title = film.get("title")
                if isinstance(title, str) and title.casefold() in lowered:
                    film_id = film.get("id")
                    if isinstance(film_id, (str, int)) and not isinstance(film_id, bool):
                        if str(film_id) not in excluded_ids:
                            current["excluded_ids"].append(film_id)
                            excluded_ids.add(str(film_id))
            excluded_genres = set(current["excluded_genres"])
            for genre in kino.GENRES:
                if re.search(rf"(?<!\w){re.escape(genre)}(?!\w)", lowered):
                    if genre not in excluded_genres:
                        current["excluded_genres"].append(genre)
                        excluded_genres.add(genre)

        unavailable = {str(value) for value in current["seen_ids"] + current["excluded_ids"]}
        excluded_genres = set(current["excluded_genres"])
        candidates = [
            film
            for film in self.films
            if str(film.get("id")) not in unavailable
            and not excluded_genres.intersection(film.get("genres", []))
        ]
        if not candidates:
            if not clarification_answer:
                current["last_query"] = query
            self._save_state(chat_id, current)
            await self._send(
                bot,
                chat_id,
                "No new matching films are available. Use /new to start over.",
            )
            return
        output = StringIO()
        try:
            max_clarify_turns = _max_clarify_turns()
            with redirect_stdout(output):
                outcome, ids = self.picker(self.client, self.model, query, candidates)
        except Exception:
            if not clarification_answer:
                current["last_query"] = query
            self._save_state(chat_id, current)
            await self._send(bot, chat_id, "I couldn't complete that request. Please try again.")
            return

        current["last_query"] = query
        response = output.getvalue().strip()
        candidate_ids = {str(film.get("id")) for film in candidates}
        if outcome == "ok" and (
            not ids
            or len({str(film_id) for film_id in ids}) != len(ids)
            or any(str(film_id) not in candidate_ids for film_id in ids)
        ):
            outcome = "invalid"
            response = "I couldn't complete that request. Please try again."
        if outcome == "clarify":
            if current["clarify_turns"] >= max_clarify_turns:
                outcome = "no_match"
                response = "No matching films found after clarification."
                current["pending_clarify"] = None
                current["clarify_turns"] = 0
            else:
                response = response or "Could you clarify your request?"
                current["pending_clarify"] = response
                current["clarify_turns"] += 1
        else:
            current["pending_clarify"] = None
            current["clarify_turns"] = 0

        if outcome == "ok":
            seen = {str(film_id) for film_id in current["seen_ids"]}
            for film_id in ids:
                if str(film_id) not in seen:
                    current["seen_ids"].append(film_id)
                    seen.add(str(film_id))
        self._save_state(chat_id, current)

        if outcome not in {"ok", "no_match", "clarify"} and not response:
            response = "I couldn't complete that request. Please try again."
        if not response:
            response = "No recommendation was returned. Please try another request."
        await self._send(bot, chat_id, response)


def build_dispatcher(
    *,
    client: Any,
    model: str,
    films: list[dict[str, Any]],
    state_path: str | Path | None = None,
    picker: PickFunction | None = None,
) -> Dispatcher:
    dispatcher = telegram.create_dispatcher()
    router = Router(name="movie-buff")
    BotHandlers(
        client=client,
        model=model,
        films=films,
        state_path=state_path,
        picker=picker,
    ).register(router)
    dispatcher.include_router(router)
    return dispatcher


async def run_bot() -> int:
    configure_logging()
    settings = kino.load_settings()
    if not settings.get("api_key"):
        print("error: OPENAI_API_KEY is missing from .env", file=sys.stderr)
        return 2
    if not settings.get("model"):
        print("error: MODEL is missing from .env", file=sys.stderr)
        return 2

    try:
        films = kino.load_catalog()
        client = kino.make_client(settings)
        bot = telegram.create_bot()
        dispatcher = build_dispatcher(client=client, model=settings["model"], films=films)
    except Exception as error:
        print(f"error: cannot start bot ({type(error).__name__})", file=sys.stderr)
        return 2

    await telegram.start_polling(dispatcher, bot)
    return 0


def main() -> int:
    return asyncio.run(run_bot())


if __name__ == "__main__":
    raise SystemExit(main())
