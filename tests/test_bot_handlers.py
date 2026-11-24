"""Step 25: Telegram commands, callbacks, and free-text selection."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from aiogram.types import InlineKeyboardMarkup

from movie_bluff_ai_bot import __main__ as bot_main
from movie_bluff_ai_bot.state import load_chat_state, new_state, save_chat_state


class FakeBot:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send_message(self, **kwargs: Any) -> None:
        self.sent.append(kwargs)


class FakeMessage:
    def __init__(self, text: str, bot: FakeBot, chat_id: int = 42) -> None:
        self.text = text
        self.bot = bot
        self.chat = type("Chat", (), {"id": chat_id})()


class FakeCallback:
    def __init__(self, data: str, message: FakeMessage | None) -> None:
        self.data = data
        self.message = message
        self.bot = message.bot if message is not None else None
        self.answer_count = 0

    async def answer(self) -> None:
        self.answer_count += 1


def _handlers(
    catalog: list[dict[str, Any]],
    path: Path,
    picker: Any,
) -> bot_main.BotHandlers:
    return bot_main.BotHandlers(
        client=object(),
        model="offline-model",
        films=catalog,
        state_path=path,
        picker=picker,
    )


def test_start_sends_inline_genre_keyboard(catalog: list[dict[str, Any]], tmp_path: Path) -> None:
    bot = FakeBot()
    handler = _handlers(catalog, tmp_path / "state.json", lambda *_args: ("no_match", []))

    asyncio.run(handler.start(FakeMessage("/start", bot)))

    sent = bot.sent[0]
    assert "choose a genre" in sent["text"].lower()
    markup = sent["reply_markup"]
    assert isinstance(markup, InlineKeyboardMarkup)
    buttons = [button for row in markup.inline_keyboard for button in row]
    assert buttons
    assert all(button.callback_data.startswith("genre:") for button in buttons)
    assert all(bot_main.telegram.callback_data_allowed(button.callback_data) for button in buttons)


def test_help_new_more_and_unknown_command(
    catalog: list[dict[str, Any]],
    tmp_path: Path,
) -> None:
    bot = FakeBot()
    path = tmp_path / "state.json"
    stored = new_state()
    stored["seen_ids"] = ["f-001"]
    stored["last_query"] = "a quiet film"
    save_chat_state(42, stored, path)
    selected: list[str] = []

    def picker(_client: Any, _model: str, query: str, _films: Any) -> tuple[str, list[str]]:
        selected.append(query)
        print("A quiet film")
        return ("ok", ["f-002"])

    handler = _handlers(catalog, path, picker)
    message = FakeMessage("/help", bot)

    asyncio.run(handler.help(message))
    asyncio.run(handler.unknown(FakeMessage("/unknown", bot)))
    assert "/start" in bot.sent[0]["text"]
    assert "/start" in bot.sent[1]["text"]
    assert selected == []

    asyncio.run(handler.more(FakeMessage("/more", bot)))
    assert selected == ["a quiet film"]
    assert load_chat_state(42, path)["seen_ids"] == ["f-001", "f-002"]

    asyncio.run(handler.new(FakeMessage("/new", bot)))
    cleared = load_chat_state(42, path)
    assert cleared["seen_ids"] == []
    assert cleared["last_query"] is None
    assert "new" in bot.sent[-1]["text"].lower()


def test_genre_callback_answers_every_callback_and_calls_pick(
    catalog: list[dict[str, Any]], tmp_path: Path
) -> None:
    bot = FakeBot()
    path = tmp_path / "state.json"
    selected: list[str] = []

    def picker(_client: Any, _model: str, query: str, _films: Any) -> tuple[str, list[str]]:
        selected.append(query)
        print("Recommended film")
        return ("ok", ["f-001"])

    handler = _handlers(catalog, path, picker)
    message = FakeMessage("", bot)
    accepted = FakeCallback("genre:drama", message)
    rejected = FakeCallback("genre:query-injection", message)
    no_message = FakeCallback("genre:drama", None)

    asyncio.run(handler.callback(accepted))
    asyncio.run(handler.callback(rejected))
    asyncio.run(handler.callback(no_message))

    assert accepted.answer_count == 1
    assert rejected.answer_count == 1
    assert no_message.answer_count == 1
    assert selected == ["Recommend a drama film."]
    assert load_chat_state(42, path)["seen_ids"] == ["f-001"]


def test_free_text_calls_pick_and_persists_seen_ids(
    catalog: list[dict[str, Any]], tmp_path: Path
) -> None:
    bot = FakeBot()
    path = tmp_path / "state.json"
    received: list[tuple[Any, str, str, Any]] = []
    client = object()

    def picker(
        passed_client: Any,
        model: str,
        query: str,
        films: Any,
    ) -> tuple[str, list[str | int]]:
        received.append((passed_client, model, query, films))
        print("Alpha (1999)")
        return ("ok", ["f-001", "f-003"])

    handler = bot_main.BotHandlers(
        client=client,
        model="selected-model",
        films=catalog,
        state_path=path,
        picker=picker,
    )
    query = "қазақша қысқа фильм"

    asyncio.run(handler.text(FakeMessage(query, bot)))

    assert received == [(client, "selected-model", query, catalog)]
    stored = load_chat_state(42, path)
    assert stored["last_query"] == query
    assert stored["seen_ids"] == ["f-001", "f-003"]
    assert "Alpha (1999)" in bot.sent[0]["text"]


def test_state_is_separate_between_chats(catalog: list[dict[str, Any]], tmp_path: Path) -> None:
    bot = FakeBot()
    path = tmp_path / "state.json"

    def picker(_client: Any, _model: str, query: str, _films: Any) -> tuple[str, list[str]]:
        return ("ok", ["f-001"] if "first" in query else ["f-002"])

    handler = _handlers(catalog, path, picker)
    asyncio.run(handler.text(FakeMessage("first request", bot, chat_id=101)))
    asyncio.run(handler.text(FakeMessage("second request", bot, chat_id=202)))

    assert load_chat_state(101, path)["seen_ids"] == ["f-001"]
    assert load_chat_state(202, path)["seen_ids"] == ["f-002"]


def test_model_error_is_answered_without_crashing(
    catalog: list[dict[str, Any]], tmp_path: Path
) -> None:
    bot = FakeBot()

    def picker(*_args: Any) -> tuple[str, list[str]]:
        return ("no_connection", [])

    handler = _handlers(catalog, tmp_path / "state.json", picker)

    asyncio.run(handler.text(FakeMessage("a film", bot)))

    assert "try again" in bot.sent[0]["text"].lower()


def test_dispatcher_registers_commands_callbacks_and_fallbacks(
    catalog: list[dict[str, Any]], tmp_path: Path
) -> None:
    dispatcher = bot_main.build_dispatcher(
        client=object(),
        model="offline-model",
        films=catalog,
        state_path=tmp_path / "state.json",
        picker=lambda *_args: ("no_match", []),
    )

    assert len(dispatcher.sub_routers) == 1
    router = dispatcher.sub_routers[0]
    assert len(router.message.handlers) >= 6
    assert len(router.callback_query.handlers) == 1


def test_bot_library_loggers_use_warning_level() -> None:
    bot_main.configure_logging()

    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
    assert logging.getLogger("aiogram").level == logging.WARNING
