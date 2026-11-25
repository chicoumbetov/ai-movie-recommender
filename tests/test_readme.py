"""Step 30: README claims and real-run numbers stay tied to repository evidence."""

from __future__ import annotations

import json
import re
from pathlib import Path

from show import aggregate, format_report, read_rows

ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"


def test_readme_has_lean_claim_structure_and_required_commands() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    first_line = readme.splitlines()[0]

    assert first_line == "# Common 100%; Rare points 1–2; Legendary points 1 and 4"
    for heading in (
        "## Purpose",
        "## Quick start",
        "## Five questions from lecture 1",
        "## How selection works",
        "## Real evaluation",
        "## Catalog and provenance",
        "## Model memory experiment",
        "## Assignment questions",
        "## Scope and limits",
    ):
        assert heading in readme

    for command in (
        "uv sync --frozen",
        'uv run kino.py "..."',
        "uv run check.py",
        "uv run show.py",
        "uv run pytest",
    ):
        assert command in readme

    assert "This product uses the TMDB API but is not endorsed or certified by TMDB." in readme
    assert "tmdb_id" in readme
    assert "wikipedia_url" in readme
    assert "verified_by" in readme
    assert "English-language (`en-US`) fields" in readme
    assert "canonical English list" in readme
    assert "not generated from model memory" in readme.lower()
    assert re.search(r"(?:kino|check|utils|scripts/memory_experiment)\.py:\d+", readme)
    assert not re.search(r"\b(?:TODO|TBD|PLACEHOLDER|lorem ipsum)\b", readme, re.IGNORECASE)


def test_readme_real_run_blocks_match_saved_outputs_and_journal() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    output = (ROOT / "real_run_output.txt").read_text(encoding="utf-8")
    calls = [row for row in read_rows(ROOT / "calls.jsonl") if row.get("model") == "qwen3.5:4b"]

    assert format_report(aggregate(calls)) in readme

    check_start = output.rfind("Outcome counts:")
    assert check_start >= 0
    check_block = output[check_start:].split("command exit:", 1)[0].rstrip()
    assert check_block in readme

    memory_start = output.rfind("Outcome: ok")
    assert memory_start >= 0
    memory_block = output[memory_start:].split("command exit:", 1)[0].strip()
    assert memory_block in readme


def test_readme_catalog_date_and_memory_answers_come_from_artifacts() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    sources = json.loads((ROOT / "catalog_sources.json").read_text(encoding="utf-8"))
    memory_rows = read_rows(ROOT / "memory_calls.jsonl")

    retrieved_dates = {source["retrieved_at"][:10] for source in sources}
    assert len(retrieved_dates) == 1
    assert next(iter(retrieved_dates)) in readme
    assert "2026-11-24T11:32:41Z" in readme
    assert "The Godfather" in readme
    assert "Casablanca" in readme
    assert "Jaws" in readme
    assert "Alien" in readme
    assert "Titanic" in readme
    for source in (
        "https://en.wikipedia.org/wiki/Ayka",
        "https://en.wikipedia.org/wiki/Mongol_(film)",
        "https://en.wikipedia.org/wiki/The_Old_Man_(2012_film)",
        "https://fr.wikipedia.org/wiki/Baikonur",
    ):
        assert source in readme
    for verified_runtime in ("100", "125", "102", "94"):
        assert verified_runtime in readme
    for runtime_row in (
        "| Ayka | 100 min | 120 min |",
        "| Mongol: The Rise of Genghis Khan | 125 min | 121 min |",
        "| The Old Man (2012) | 102 min | 106 min |",
        "| Baikonur | 94 min | 107 min |",
    ):
        assert runtime_row in readme
    assert "Films compared: 10" in readme
    assert "Discrepancies: 5" in readme
    assert len(memory_rows) == 1
    assert len(memory_rows[0]["request"]["titles"]) == 10
