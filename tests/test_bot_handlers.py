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


def test_more_excludes_seen_ids_before_choice_and_returns_no_match_when_exhausted(
    catalog: list[dict[str, Any]], tmp_path: Path
) -> None:
    bot = FakeBot()
    path = tmp_path / "state.json"
    calls: list[list[str | int]] = []

    def picker(
        _client: Any, _model: str, _query: str, films: list[dict[str, Any]]
    ) -> tuple[str, list[str]]:
        calls.append([film["id"] for film in films])
        return ("ok", [str(films[0]["id"])])

    handler = _handlers(catalog, path, picker)
    asyncio.run(handler.text(FakeMessage("quiet drama", bot)))
    asyncio.run(handler.more(FakeMessage("/more", bot)))
    asyncio.run(handler.more(FakeMessage("/more", bot)))
    asyncio.run(handler.more(FakeMessage("/more", bot)))

    assert calls[0] == [film["id"] for film in catalog]
    assert "f-001" not in calls[1]
    assert load_chat_state(42, path)["seen_ids"] == ["f-001", "f-002", "f-003", "f-004"]

    def exhausted(*_args: Any) -> tuple[str, list[str]]:
        raise AssertionError("picker must not run when no new candidates remain")

    asyncio.run(_handlers(catalog, path, exhausted).more(FakeMessage("/more", bot)))
    assert "no new" in bot.sent[-1]["text"].lower()


def test_explicit_title_and_genre_exclusions_persist_and_filter_candidates(
    catalog: list[dict[str, Any]], tmp_path: Path
) -> None:
    bot = FakeBot()
    path = tmp_path / "state.json"
    received: list[list[str | int]] = []

    def picker(
        _client: Any, _model: str, _query: str, films: list[dict[str, Any]]
    ) -> tuple[str, list[str]]:
        received.append([film["id"] for film in films])
        return ("no_match", [])

    handler = _handlers(catalog, path, picker)
    title = catalog[0]["title"]
    asyncio.run(handler.text(FakeMessage(f"Already watched {title}; without horror", bot)))

    stored = load_chat_state(42, path)
    assert catalog[0]["id"] in stored["excluded_ids"]
    assert "horror" in stored["excluded_genres"]
    assert catalog[0]["id"] not in received[0]
    assert all("horror" not in film["genres"] for film in catalog if film["id"] in received[0])
    assert load_chat_state(42, path)["excluded_ids"] == stored["excluded_ids"]


def test_picker_repeat_is_invalid_and_its_printed_film_is_discarded(
    catalog: list[dict[str, Any]], tmp_path: Path
) -> None:
    bot = FakeBot()

    def picker(*_args: Any) -> tuple[str, list[str]]:
        print("A film that was already shown")
        return ("ok", ["f-001"])

    handler = _handlers(catalog, tmp_path / "state.json", picker)
    asyncio.run(handler.text(FakeMessage("first", bot)))
    asyncio.run(handler.more(FakeMessage("/more", bot)))

    assert "already shown" not in bot.sent[-1]["text"].lower()
    assert "couldn&#x27;t complete" in bot.sent[-1]["text"].lower()


def test_clarify_answer_merges_with_query_and_clears_pending_state(
    catalog: list[dict[str, Any]],
    tmp_path: Path,
) -> None:
    bot = FakeBot()
    path = tmp_path / "state.json"
    queries: list[str] = []
    original = "A quiet movie from Kazakhstan"
    answer = "Preferably from the 1990s"

    def picker(_client: Any, _model: str, query: str, _films: Any) -> tuple[str, list[str]]:
        queries.append(query)
        if len(queries) == 1:
            print("Which decade do you prefer?")
            return ("clarify", [])
        print("Mongol (2007)")
        return ("ok", ["f-001"])

    handler = _handlers(catalog, path, picker)
    asyncio.run(handler.text(FakeMessage(original, bot)))

    waiting = load_chat_state(42, path)
    assert waiting["pending_clarify"] == "Which decade do you prefer?"
    assert waiting["clarify_turns"] == 1
    assert waiting["last_query"] == original

    asyncio.run(handler.text(FakeMessage(answer, bot)))

    assert queries == [original, f"{original}\n{answer}"]
    finished = load_chat_state(42, path)
    assert finished["last_query"] == f"{original}\n{answer}"
    assert finished["pending_clarify"] is None
    assert finished["clarify_turns"] == 0
    assert finished["seen_ids"] == ["f-001"]
    assert "Mongol" in bot.sent[-1]["text"]


def test_second_clarify_result_after_turn_limit_becomes_no_match(
    catalog: list[dict[str, Any]],
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("MAX_CLARIFY_TURNS", "1")
    bot = FakeBot()
    path = tmp_path / "state.json"
    queries: list[str] = []

    def picker(_client: Any, _model: str, query: str, _films: Any) -> tuple[str, list[str]]:
        queries.append(query)
        print("Please add another detail.")
        return ("clarify", [])

    handler = _handlers(catalog, path, picker)
    asyncio.run(handler.text(FakeMessage("A short drama", bot)))
    asyncio.run(handler.text(FakeMessage("Under two hours", bot)))

    assert queries == ["A short drama", "A short drama\nUnder two hours"]
    final_state = load_chat_state(42, path)
    assert final_state["pending_clarify"] is None
    assert final_state["clarify_turns"] == 0
    assert "no matching" in bot.sent[-1]["text"].lower()
    assert "please add another detail" not in bot.sent[-1]["text"].lower()


def test_command_is_handled_while_clarification_is_pending(
    catalog: list[dict[str, Any]], tmp_path: Path
) -> None:
    bot = FakeBot()
    path = tmp_path / "state.json"
    queries: list[str] = []

    def picker(_client: Any, _model: str, query: str, _films: Any) -> tuple[str, list[str]]:
        queries.append(query)
        print("What mood do you want?")
        return ("clarify", [])

    handler = _handlers(catalog, path, picker)
    asyncio.run(handler.text(FakeMessage("Recommend a movie", bot)))
    asyncio.run(handler.help(FakeMessage("/help", bot)))

    assert queries == ["Recommend a movie"]
    assert load_chat_state(42, path)["pending_clarify"] == "What mood do you want?"
    assert "/start" in bot.sent[-1]["text"]


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
    registered = [handler.callback.__name__ for handler in router.message.handlers]
    assert registered.index("help") < registered.index("text")
    assert registered.index("unknown") < registered.index("text")


def test_bot_library_loggers_use_warning_level() -> None:
    bot_main.configure_logging()

    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
    assert logging.getLogger("aiogram").level == logging.WARNING
