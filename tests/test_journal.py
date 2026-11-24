"""Step 11: structured call journal."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any


def _usage() -> SimpleNamespace:
    return SimpleNamespace(prompt_tokens=100, completion_tokens=20, total_tokens=120)


def _log(path: Path, **overrides: Any) -> None:
    from utils import log

    params: dict[str, Any] = {
        "model": "qwen3.5:4b",
        "request": {"query": "тихий фильм", "ids": ["f-001", "f-002"]},
        "outcome": "ok",
        "step": "choice",
        "started": 100.0,
        "completion": SimpleNamespace(usage=_usage()),
        "path": path,
    }
    params.update(overrides)
    log(**params)


def test_one_line_per_call(tmp_path: Path) -> None:
    path = tmp_path / "calls.jsonl"
    _log(path, started=100.0)
    _log(path, started=101.0, outcome="no_match", step="filters")

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert all(json.loads(line) for line in lines)


def test_mandatory_fields_and_iso_time(tmp_path: Path) -> None:
    path = tmp_path / "calls.jsonl"
    _log(path)
    row = json.loads(path.read_text(encoding="utf-8"))

    for field in ("time", "model", "request", "outcome", "step"):
        assert field in row
    assert row["time"].endswith("Z")
    parsed = datetime.fromisoformat(row["time"].replace("Z", "+00:00"))
    assert parsed.utcoffset().total_seconds() == 0
    assert row["step"] == "choice"
    assert row["model"] == "qwen3.5:4b"
    assert row["request"] == {"query": "тихий фильм", "ids": ["f-001", "f-002"]}


def test_usage_and_seconds_are_written(tmp_path: Path) -> None:
    path = tmp_path / "calls.jsonl"
    _log(path, started=100.0)
    row = json.loads(path.read_text(encoding="utf-8"))
    assert row["usage"]["prompt_tokens"] == 100
    assert row["usage"]["completion_tokens"] == 20
    assert "seconds" in row
    assert row["seconds"] >= 0


def test_unknown_price_is_zero(tmp_path: Path) -> None:
    path = tmp_path / "calls.jsonl"
    _log(path, model="unknown-model")
    row = json.loads(path.read_text(encoding="utf-8"))
    assert row["usd"] == 0


def test_rejected_is_written_when_present(tmp_path: Path) -> None:
    path = tmp_path / "calls.jsonl"
    _log(path, outcome="invalid", rejected=["f-999"])
    row = json.loads(path.read_text(encoding="utf-8"))
    assert row["rejected"] == ["f-999"]


def test_utf8_is_not_escaped(tmp_path: Path) -> None:
    path = tmp_path / "calls.jsonl"
    _log(path, request={"query": "әлем жоқ", "ids": []})
    raw = path.read_text(encoding="utf-8")
    assert "әлем" in raw
    assert "\\u04d9" not in raw


def test_write_error_warns_without_crashing(tmp_path: Path, capsys: Any) -> None:
    missing_parent = tmp_path / "missing" / "calls.jsonl"
    _log(missing_parent)
    captured = capsys.readouterr()
    assert "warning" in captured.err.lower()
    assert not missing_parent.exists()


def test_no_catalog_payload_required(tmp_path: Path) -> None:
    path = tmp_path / "calls.jsonl"
    _log(path, request={"query": "x", "ids": ["f-001"]})
    row = json.loads(path.read_text(encoding="utf-8"))
    assert set(row["request"]) == {"query", "ids"}
