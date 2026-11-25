"""Step 29: committed real-run artifacts match the evaluation inputs."""

from __future__ import annotations

import json
import re
from pathlib import Path

from check import load_queries

CALLS_PATH = Path("calls.jsonl")
MEMORY_PATH = Path("memory_calls.jsonl")
OUTPUT_PATH = Path("real_run_output.txt")
ROOT_CATALOG = Path("films.json")
RUNTIME_CATALOG = Path("data/en/films.json")
STUB_MODEL = re.compile(r"stub|fake|mock|test|shadow|model-xxxxxx", re.IGNORECASE)


def _rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_real_run_journals_cover_queries_and_memory_experiment() -> None:
    queries = {item["query"] for item in load_queries()}
    call_rows = _rows(CALLS_PATH)
    memory_rows = _rows(MEMORY_PATH)
    output = OUTPUT_PATH.read_text(encoding="utf-8")

    called_queries = {
        row["request"]["query"]
        for row in call_rows
        if row.get("step") == "filters" and isinstance(row.get("request"), dict)
    }
    assert queries <= called_queries
    assert call_rows
    assert all(not STUB_MODEL.search(str(row["model"])) for row in call_rows)
    assert {row["outcome"] for row in call_rows} >= {"ok", "no_match"}
    assert len(memory_rows) == 1
    assert not STUB_MODEL.search(str(memory_rows[0]["model"]))
    assert len(memory_rows[0]["request"]["titles"]) == 10
    assert "Films compared: 10" in output


def test_root_catalog_is_the_runtime_catalog_copy() -> None:
    """The mentor's probe reads root films.json; S03 reads data/en/films.json."""
    assert json.loads(ROOT_CATALOG.read_text(encoding="utf-8")) == json.loads(
        RUNTIME_CATALOG.read_text(encoding="utf-8")
    )
