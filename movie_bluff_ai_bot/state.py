"""Persistent, secret-free Telegram conversation state."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict

DEFAULT_STATE_PATH = Path("state.json")
STATE_FIELDS = frozenset(
    {
        "seen_ids",
        "excluded_ids",
        "excluded_genres",
        "last_query",
        "last_filters",
        "pending_clarify",
        "clarify_turns",
        "updated_at",
    }
)
FILTER_FIELDS = frozenset(
    {"max_minutes", "year_from", "year_to", "languages", "exclude_genres", "must_genres"}
)


class BotState(TypedDict):
    seen_ids: list[str | int]
    excluded_ids: list[str | int]
    excluded_genres: list[str]
    last_query: str | None
    last_filters: dict[str, Any] | None
    pending_clarify: str | None
    clarify_turns: int
    updated_at: str


def _state_path(path: str | Path | None) -> Path:
    if path is not None:
        return Path(path)
    return Path(os.environ.get("BOT_STATE_PATH", str(DEFAULT_STATE_PATH)))


def new_state() -> BotState:
    """Return an empty state with every required field initialized."""
    return {
        "seen_ids": [],
        "excluded_ids": [],
        "excluded_genres": [],
        "last_query": None,
        "last_filters": None,
        "pending_clarify": None,
        "clarify_turns": 0,
        "updated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def _validate_state(value: Any) -> BotState:
    if not isinstance(value, dict):
        raise ValueError("state must be a JSON object")
    unknown = value.keys() - STATE_FIELDS
    missing = STATE_FIELDS - value.keys()
    if unknown:
        raise ValueError(f"unsupported state field(s): {', '.join(sorted(unknown))}")
    if missing:
        raise ValueError(f"missing state field(s): {', '.join(sorted(missing))}")

    for field in ("seen_ids", "excluded_ids"):
        ids = value[field]
        if not isinstance(ids, list) or any(
            not isinstance(film_id, (str, int)) or isinstance(film_id, bool) for film_id in ids
        ):
            raise ValueError(f"{field} must be a list of string or integer IDs")
    if not isinstance(value["excluded_genres"], list) or any(
        not isinstance(genre, str) for genre in value["excluded_genres"]
    ):
        raise ValueError("excluded_genres must be a list of strings")
    if value["last_query"] is not None and not isinstance(value["last_query"], str):
        raise ValueError("last_query must be a string or null")
    filters = value["last_filters"]
    if filters is not None and (not isinstance(filters, dict) or filters.keys() - FILTER_FIELDS):
        raise ValueError("last_filters must contain only supported filter fields")
    if value["pending_clarify"] is not None and not isinstance(value["pending_clarify"], str):
        raise ValueError("pending_clarify must be a string or null")
    turns = value["clarify_turns"]
    if not isinstance(turns, int) or isinstance(turns, bool) or turns < 0:
        raise ValueError("clarify_turns must be a non-negative integer")
    if not isinstance(value["updated_at"], str) or not value["updated_at"].strip():
        raise ValueError("updated_at must be a non-empty string")

    return BotState(
        seen_ids=value["seen_ids"],
        excluded_ids=value["excluded_ids"],
        excluded_genres=value["excluded_genres"],
        last_query=value["last_query"],
        last_filters=value["last_filters"],
        pending_clarify=value["pending_clarify"],
        clarify_turns=value["clarify_turns"],
        updated_at=value["updated_at"],
    )


def load_state(path: str | Path | None = None) -> BotState:
    """Load state; a missing file is a clean start and corrupt files warn then recover."""
    target = _state_path(path)
    try:
        raw = target.read_text(encoding="utf-8")
        return _validate_state(json.loads(raw))
    except FileNotFoundError:
        return new_state()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        print(
            f"warning: cannot load bot state {target}: {error}; starting with clean state",
            file=sys.stderr,
        )
        return new_state()


def _load_chat_document(path: Path) -> tuple[dict[str, BotState], BotState | None]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("chat state must be a JSON object")
    if raw.keys() == STATE_FIELDS:
        return ({}, _validate_state(raw))

    chat_states: dict[str, BotState] = {}
    for chat_id, value in raw.items():
        if not isinstance(chat_id, str) or not chat_id.lstrip("-").isdigit():
            raise ValueError("chat state keys must be numeric chat IDs")
        chat_states[chat_id] = _validate_state(value)
    return (chat_states, None)


def load_chat_state(chat_id: int, path: str | Path | None = None) -> BotState:
    """Load one chat's state from a per-chat state document."""
    target = _state_path(path)
    try:
        chat_states, legacy_state = _load_chat_document(target)
        if legacy_state is not None:
            return legacy_state
        return chat_states.get(str(chat_id), new_state())
    except FileNotFoundError:
        return new_state()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        print(
            f"warning: cannot load bot state {target}: {error}; starting with clean state",
            file=sys.stderr,
        )
        return new_state()


def save_chat_state(
    chat_id: int,
    value: Mapping[str, Any],
    path: str | Path | None = None,
) -> None:
    """Atomically update one chat's state while preserving other chats."""
    clean_state = _validate_state(dict(value))
    target = _state_path(path)
    chat_states: dict[str, BotState] = {}
    try:
        chat_states, legacy_state = _load_chat_document(target)
        if legacy_state is not None:
            chat_states[str(chat_id)] = legacy_state
    except FileNotFoundError:
        pass
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        print(
            f"warning: cannot load bot state {target}: {error}; starting with clean state",
            file=sys.stderr,
        )

    chat_states[str(chat_id)] = clean_state
    temporary = target.with_name(f"{target.name}.tmp")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(chat_states, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def save_state(state: Mapping[str, Any], path: str | Path | None = None) -> None:
    """Atomically save a validated state object without accepting secret fields."""
    clean_state = _validate_state(dict(state))
    target = _state_path(path)
    temporary = target.with_name(f"{target.name}.tmp")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(clean_state, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
