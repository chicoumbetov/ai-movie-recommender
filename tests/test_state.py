"""Step 23: persistent bot state storage."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from movie_bluff_ai_bot import state


def _sample_state() -> dict[str, Any]:
    return {
        "seen_ids": ["f-001", 2],
        "excluded_ids": ["f-003"],
        "excluded_genres": ["horror"],
        "last_query": "a short film",
        "last_filters": {"max_minutes": 100, "year_from": 1990},
        "pending_clarify": "Which mood do you prefer?",
        "clarify_turns": 1,
        "updated_at": "2026-11-24T12:00:00Z",
    }


def test_state_roundtrip_and_restart_persistence(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    expected = _sample_state()

    state.save_state(expected, path)
    after_restart = state.load_state(path)

    assert after_restart == expected
    assert json.loads(path.read_text(encoding="utf-8")) == expected


def test_corrupt_state_warns_and_returns_clean_default(tmp_path: Path, capsys: Any) -> None:
    path = tmp_path / "state.json"
    path.write_text("{broken", encoding="utf-8")

    loaded = state.load_state(path)

    assert set(loaded) == {
        "seen_ids",
        "excluded_ids",
        "excluded_genres",
        "last_query",
        "last_filters",
        "pending_clarify",
        "clarify_turns",
        "updated_at",
    }
    assert loaded["seen_ids"] == []
    assert loaded["excluded_ids"] == []
    assert loaded["excluded_genres"] == []
    assert loaded["last_query"] is None
    assert loaded["last_filters"] is None
    assert loaded["pending_clarify"] is None
    assert loaded["clarify_turns"] == 0
    assert "warning" in capsys.readouterr().err.lower()


def test_invalid_shape_warns_and_returns_clean_default(tmp_path: Path, capsys: Any) -> None:
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"seen_ids": "not-a-list"}), encoding="utf-8")

    loaded = state.load_state(path)

    assert loaded["seen_ids"] == []
    assert loaded["clarify_turns"] == 0
    assert "warning" in capsys.readouterr().err.lower()


def test_atomic_write_replaces_target_and_removes_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "nested" / "state.json"
    expected = _sample_state()
    real_replace = os.replace
    replaced: list[tuple[Path, Path]] = []

    def inspect_replace(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> None:
        source_path = Path(source)
        target_path = Path(target)
        assert source_path.exists()
        assert json.loads(source_path.read_text(encoding="utf-8")) == expected
        replaced.append((source_path, target_path))
        real_replace(source, target)

    monkeypatch.setattr(state.os, "replace", inspect_replace)
    state.save_state(expected, path)

    assert replaced == [(path.with_name("state.json.tmp"), path)]
    assert path.exists()
    assert not path.with_name("state.json.tmp").exists()
    assert state.load_state(path) == expected


def test_bot_state_path_environment_variable_is_respected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "custom" / "bot-state.json"
    monkeypatch.setenv("BOT_STATE_PATH", str(path))
    expected = _sample_state()

    state.save_state(expected)

    assert path.exists()
    assert state.load_state() == expected


def test_secrets_cannot_be_added_to_saved_state(tmp_path: Path) -> None:
    unsafe = {**_sample_state(), "TELEGRAM_BOT_TOKEN": "do-not-save-this"}

    with pytest.raises(ValueError, match="unsupported state field"):
        state.save_state(unsafe, tmp_path / "state.json")

    assert not (tmp_path / "state.json").exists()
