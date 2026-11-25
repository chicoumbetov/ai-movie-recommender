"""Step 28: catalog-free model memory comparison."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts import memory_experiment as memory


def _answers() -> list[dict[str, Any]]:
    return [
        {"title": film.title, "year": film.year, "minutes": film.minutes} for film in memory.FILMS
    ]


def test_exact_answers_have_no_discrepancies_and_use_memory_journal(
    fake_client_factory: Any, tmp_path: Path
) -> None:
    journal = tmp_path / "memory_calls.jsonl"
    client = fake_client_factory([memory.MemoryRecall(films=_answers())])

    report = memory.run_experiment(client, "offline-model", journal_path=journal)

    assert len(memory.FILMS) == 10
    assert report.discrepancy_count == 0
    assert report.compared_films == 10
    assert client.calls[0]["response_format"] is memory.MemoryRecall
    request_text = client.calls[0]["messages"][1]["content"]
    assert "catalog" not in request_text.lower()
    row = json.loads(journal.read_text(encoding="utf-8"))
    assert row["step"] == "memory"
    assert len(row["request"]["titles"]) == 10
    assert "year" not in row["request"]


def test_wrong_year_and_runtime_count_as_two_discrepancies(
    fake_client_factory: Any, tmp_path: Path
) -> None:
    answers = _answers()
    answers[0]["year"] += 1
    answers[1]["minutes"] += 1
    client = fake_client_factory([memory.MemoryRecall(films=answers)])

    report = memory.run_experiment(
        client,
        "offline-model",
        journal_path=tmp_path / "memory_calls.jsonl",
    )

    assert report.discrepancy_count == 2
    assert report.discrepancies == [
        {"title": memory.FILMS[0].title, "field": "year", "expected": 1972, "actual": 1973},
        {"title": memory.FILMS[1].title, "field": "minutes", "expected": 142, "actual": 143},
    ]
