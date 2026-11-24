"""Telegram transport helpers built on aiogram's long-polling client."""

from __future__ import annotations

import asyncio
import html
import ipaddress
import os
import re
import sys
from collections.abc import Awaitable, Callable, Collection
from typing import Any
from urllib.parse import urlsplit

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter, TelegramServerError

from kino import GENRES

DEFAULT_API_BASE = "https://api.telegram.org"
MAX_MESSAGE_CHARS = 4096
MAX_SEND_ATTEMPTS = 3
CALLBACK_DATA_ALLOWLIST = frozenset(f"genre:{genre}" for genre in GENRES)
_ESCAPED_TOKEN = re.compile(r"&(?:amp|lt|gt|quot|#x27);|.", re.DOTALL)
Sleep = Callable[[float], Awaitable[None]]


def _positive_env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be a positive integer") from error
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _is_local_api(base: str) -> bool:
    host = urlsplit(base).hostname
    if host is None:
        return False
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_private or address.is_loopback


def create_bot(token: str | None = None, api_base: str | None = None) -> Bot:
    """Create a bot from explicit values or Telegram environment variables."""
    bot_token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN is missing")

    base = api_base or os.environ.get("TELEGRAM_API_BASE", "").strip() or DEFAULT_API_BASE
    api = TelegramAPIServer.from_base(base, is_local=_is_local_api(base))
    session = AiohttpSession(api=api)
    return Bot(token=bot_token, session=session)


def create_dispatcher() -> Dispatcher:
    """Create the dispatcher used by the bot application handlers."""
    return Dispatcher()


async def start_polling(
    dispatcher: Dispatcher,
    bot: Bot,
    *,
    polling_timeout: int | None = None,
) -> None:
    """Start aiogram long polling; the transport never configures a webhook."""
    timeout = (
        _positive_env_int("TELEGRAM_POLL_TIMEOUT_SECONDS", 30)
        if polling_timeout is None
        else polling_timeout
    )
    if timeout < 1:
        raise ValueError("polling_timeout must be positive")
    await dispatcher.start_polling(bot, polling_timeout=timeout)


def escape_text(text: str) -> str:
    """Escape untrusted message text for aiogram's HTML parse mode."""
    return html.escape(text, quote=True)


def split_message(text: str, max_chars: int = MAX_MESSAGE_CHARS) -> list[str]:
    """Escape text and split it into HTML-safe chunks no longer than max_chars."""
    if max_chars < 6:
        raise ValueError("max_chars must be at least 6 to preserve escaped HTML entities")
    escaped = escape_text(text)
    if not escaped:
        return []

    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for match in _ESCAPED_TOKEN.finditer(escaped):
        token = match.group()
        if length + len(token) > max_chars:
            chunks.append("".join(current))
            current = []
            length = 0
        current.append(token)
        length += len(token)
    if current:
        chunks.append("".join(current))
    return chunks


def callback_data_allowed(
    value: str,
    allowed: Collection[str] = CALLBACK_DATA_ALLOWLIST,
) -> bool:
    """Accept callback payloads only when they exactly match an allowlisted value."""
    return value in allowed


async def send_text(
    bot: Any,
    chat_id: int,
    text: str,
    *,
    max_chars: int | None = None,
    max_attempts: int = MAX_SEND_ATTEMPTS,
    sleep: Sleep = asyncio.sleep,
) -> bool:
    """Escape, split and send a message; retry Telegram throttling and transport errors."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    if max_chars is None:
        max_chars = _positive_env_int("TELEGRAM_MAX_MESSAGE_CHARS", MAX_MESSAGE_CHARS)
    max_chars = min(max_chars, MAX_MESSAGE_CHARS)

    for part in split_message(text, max_chars):
        for attempt in range(max_attempts):
            try:
                await bot.send_message(chat_id=chat_id, text=part, parse_mode="HTML")
                break
            except TelegramRetryAfter as error:
                delay = float(error.retry_after)
            except (TelegramServerError, TelegramNetworkError):
                delay = min(0.5 * (2**attempt), 5.0)

            if attempt + 1 == max_attempts:
                print(
                    "warning: Telegram send failed after retries; message was not delivered",
                    file=sys.stderr,
                )
                return False
            await sleep(delay)
    return True
