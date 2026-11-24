"""Step 18: show.py journal report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _row(
    outcome: str,
    model: str = "qwen3.5:4b",
    prompt: int = 10,
    completion: int = 5,
    usd: float = 0.0,
) -> dict[str, Any]:
    return {
        "time": "2026-01-01T00:00:00Z",
        "model": model,
        "request": {"query": "x", "ids": []},
        "outcome": outcome,
        "step": "choice",
        "usage": {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
        },
        "usd": usd,
    }


def test_aggregate_counts_outcomes_models_tokens_and_usd(tmp_path: Path) -> None:
    import show

    path = tmp_path / "calls.jsonl"
    rows = [
        _row("ok", prompt=10, completion=5, usd=0.1),
        _row("ok", prompt=20, completion=5, usd=0.2),
        _row("no_match", model="other", prompt=1, completion=1, usd=0.0),
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    report = show.aggregate(show.read_rows(path))

    assert report["calls"] == 3
    assert report["outcomes"] == {"ok": 2, "no_match": 1}
    assert report["models"] == {"qwen3.5:4b": 2, "other": 1}
    assert report["prompt_tokens"] == 31
    assert report["completion_tokens"] == 11
    assert report["total_tokens"] == 42
    assert report["usd"] == 0.3


def test_broken_lines_are_ignored(tmp_path: Path) -> None:
    import show

    path = tmp_path / "calls.jsonl"
    path.write_text(
        json.dumps(_row("ok")) + "\nnot json\n\n" + json.dumps(_row("invalid")) + "\n",
        encoding="utf-8",
    )

    rows = show.read_rows(path)

    assert len(rows) == 2
    assert [row["outcome"] for row in rows] == ["ok", "invalid"]


def test_empty_file_reports_no_calls(tmp_path: Path) -> None:
    import show

    path = tmp_path / "calls.jsonl"
    path.write_text("", encoding="utf-8")
    report = show.aggregate(show.read_rows(path))
    assert report["calls"] == 0
    assert "no calls" in show.format_report(report).lower()


def test_missing_file_reports_no_calls_and_exits_zero(tmp_path: Path, capsys: Any) -> None:
    import show

    assert show.main(tmp_path / "missing.jsonl") == 0
    assert "no calls" in capsys.readouterr().out.lower()


def test_unknown_price_is_zero(tmp_path: Path) -> None:
    import show

    path = tmp_path / "calls.jsonl"
    path.write_text(
        json.dumps(_row("ok", model="unknown-model", usd=0.0)) + "\n",
        encoding="utf-8",
    )
    report = show.aggregate(show.read_rows(path))
    assert report["usd"] == 0


def test_report_contains_all_numbers(tmp_path: Path, capsys: Any) -> None:
    import show

    path = tmp_path / "calls.jsonl"
    path.write_text(json.dumps(_row("ok", usd=0.25)) + "\n", encoding="utf-8")

    assert show.main(path) == 0
    output = capsys.readouterr().out
    assert "Calls: 1" in output
    assert "ok" in output
    assert "qwen3.5:4b" in output
    assert "0.25" in output


def test_default_path_is_used(monkeypatch: Any, tmp_path: Path, capsys: Any) -> None:
    import show

    path = tmp_path / "calls.jsonl"
    path.write_text(json.dumps(_row("ok")) + "\n", encoding="utf-8")
    monkeypatch.setattr(show, "JOURNAL_PATH", str(path))
    assert show.main() == 0
    assert "Calls: 1" in capsys.readouterr().out
