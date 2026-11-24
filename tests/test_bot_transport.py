"""Step 24: Telegram transport configuration and message delivery."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter, TelegramServerError
from aiogram.methods import SendMessage

from movie_bluff_ai_bot import telegram


def test_create_bot_uses_custom_local_bot_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:token-value")
    monkeypatch.setenv("TELEGRAM_API_BASE", "http://127.0.0.1:8081")

    bot = telegram.create_bot()

    assert bot.token == "123456:token-value"
    assert isinstance(bot.session, AiohttpSession)
    assert bot.session.api.is_local is True
    assert bot.session.api.base == "http://127.0.0.1:8081/bot{token}/{method}"
    asyncio.run(bot.session.close())


def test_create_bot_uses_default_api_when_base_is_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:token-value")
    monkeypatch.delenv("TELEGRAM_API_BASE", raising=False)

    bot = telegram.create_bot()

    assert bot.session.api.base == TelegramAPIServer.from_base("https://api.telegram.org").base
    assert bot.session.api.is_local is False
    asyncio.run(bot.session.close())


def test_missing_token_is_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        telegram.create_bot()


def test_start_polling_uses_long_polling_without_webhook(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_POLL_TIMEOUT_SECONDS", "7")

    class Dispatcher:
        def __init__(self) -> None:
            self.bots: tuple[Any, ...] = ()
            self.kwargs: dict[str, Any] = {}

        async def start_polling(self, *bots: Any, **kwargs: Any) -> None:
            self.bots = bots
            self.kwargs = kwargs

    dispatcher = Dispatcher()
    bot = object()

    asyncio.run(telegram.start_polling(dispatcher, bot))

    assert dispatcher.bots == (bot,)
    assert dispatcher.kwargs == {"polling_timeout": 7}


def test_send_text_respects_environment_message_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_MAX_MESSAGE_CHARS", "7")

    class FakeBot:
        def __init__(self) -> None:
            self.sent: list[str] = []

        async def send_message(self, *, text: str, **_kwargs: Any) -> None:
            self.sent.append(text)

    bot = FakeBot()
    assert asyncio.run(telegram.send_text(bot, 1, "long text message")) is True
    assert len(bot.sent) > 1
    assert all(len(part) <= 7 for part in bot.sent)


def test_send_text_escapes_html_and_splits_at_limit() -> None:
    class FakeBot:
        def __init__(self) -> None:
            self.sent: list[dict[str, Any]] = []

        async def send_message(self, **kwargs: Any) -> None:
            self.sent.append(kwargs)

    bot = FakeBot()
    text = "<title & friends> " + ("x" * 20)

    sent = asyncio.run(telegram.send_text(bot, 99, text, max_chars=16))

    assert sent is True
    assert len(bot.sent) > 1
    assert all(len(item["text"]) <= 16 for item in bot.sent)
    assert all(item["parse_mode"] == "HTML" for item in bot.sent)
    assert "&lt;title &amp; friends&gt;" in "".join(item["text"] for item in bot.sent)


@pytest.mark.parametrize(
    ("error_type", "delay"),
    [
        ("retry_after", 3.0),
        ("server", 0.5),
        ("network", 0.5),
    ],
)
def test_send_text_retries_rate_limit_server_and_network_errors(
    error_type: str,
    delay: float,
) -> None:
    method = SendMessage(chat_id=1, text="hello")
    if error_type == "retry_after":
        error: Exception = TelegramRetryAfter(method, "slow down", retry_after=3)
    elif error_type == "server":
        error = TelegramServerError(method, "server unavailable")
    else:
        error = TelegramNetworkError(method, "network unavailable")

    class FakeBot:
        def __init__(self) -> None:
            self.attempts = 0

        async def send_message(self, **_kwargs: Any) -> None:
            self.attempts += 1
            if self.attempts == 1:
                raise error

    bot = FakeBot()
    delays: list[float] = []

    async def sleep(seconds: float) -> None:
        delays.append(seconds)

    assert asyncio.run(telegram.send_text(bot, 1, "hello", sleep=sleep)) is True
    assert bot.attempts == 2
    assert delays == [delay]


def test_send_text_gives_up_cleanly_after_retries(capsys: Any) -> None:
    method = SendMessage(chat_id=1, text="hello")
    error = TelegramNetworkError(method, "offline")

    class OfflineBot:
        async def send_message(self, **_kwargs: Any) -> None:
            raise error

    async def no_wait(_seconds: float) -> None:
        return None

    assert (
        asyncio.run(telegram.send_text(OfflineBot(), 1, "hello", max_attempts=2, sleep=no_wait))
        is False
    )
    assert "warning" in capsys.readouterr().err.lower()


def test_callback_data_requires_allowlist_membership() -> None:
    allowed = next(iter(telegram.CALLBACK_DATA_ALLOWLIST))

    assert telegram.callback_data_allowed(allowed) is True
    assert telegram.callback_data_allowed("genre:custom-query") is False
    assert telegram.callback_data_allowed("arbitrary query text") is False
