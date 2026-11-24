"""Step 22: acceptance tests for the two-stage Rare filter flow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from schemas import Filters, Pick, Selection


def _call(
    client: Any,
    catalog: list[dict[str, Any]],
    path: Path,
) -> tuple[str, list[str | int]]:
    import kino

    return kino.pick(client, "offline-model", "short drama", catalog, journal_path=path)


def _journal(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_no_candidates_returns_no_match_without_choice_call(
    fake_client_factory: Any,
    catalog: list[dict[str, Any]],
    tmp_path: Path,
    capsys: Any,
) -> None:
    client = fake_client_factory([Filters(max_minutes=1)])

    assert _call(client, catalog, tmp_path / "calls.jsonl") == ("no_match", [])
    assert len(client.calls) == 1
    assert "no matching films" in capsys.readouterr().out.lower()
    assert [row["step"] for row in _journal(tmp_path / "calls.jsonl")] == ["filters"]


def test_selection_of_catalog_film_removed_by_filter_is_invalid(
    fake_client_factory: Any,
    catalog: list[dict[str, Any]],
    tmp_path: Path,
    capsys: Any,
) -> None:
    client = fake_client_factory(
        [
            Filters(year_to=2000),
            Selection(
                status="ok",
                reason="",
                picks=[Pick(film_id="f-002", why="A good fit.")],
            ),
        ]
    )
    path = tmp_path / "calls.jsonl"

    assert _call(client, catalog, path) == ("invalid", [])
    assert len(client.calls) == 2
    assert capsys.readouterr().out == ""
    rows = _journal(path)
    assert [row["step"] for row in rows] == ["filters", "choice"]
    assert rows[-1]["outcome"] == "invalid"
    assert rows[-1]["rejected"] == ["f-002"]


def test_choice_prompt_contains_only_filtered_candidates(
    fake_client_factory: Any,
    catalog: list[dict[str, Any]],
    tmp_path: Path,
) -> None:
    client = fake_client_factory(
        [
            Filters(max_minutes=100),
            Selection(
                status="ok",
                reason="",
                picks=[Pick(film_id="f-001", why="A good fit.")],
            ),
        ]
    )

    assert _call(client, catalog, tmp_path / "calls.jsonl") == ("ok", ["f-001"])
    choice_prompt = client.calls[1]["messages"][1]["content"]
    assert '"id": "f-001"' in choice_prompt
    assert '"id": "f-003"' in choice_prompt
    assert '"id": "f-002"' not in choice_prompt
    assert '"id": "f-004"' not in choice_prompt


@pytest.mark.parametrize(
    "filters",
    [
        Filters(must_genres=["space opera"]),
        Filters(languages=["Klingon"]),
    ],
    ids=["unknown-genre", "unknown-language"],
)
def test_unknown_genre_or_language_is_invalid(
    filters: Filters,
    fake_client_factory: Any,
    catalog: list[dict[str, Any]],
    tmp_path: Path,
) -> None:
    client = fake_client_factory([filters])
    path = tmp_path / "calls.jsonl"

    assert _call(client, catalog, path) == ("invalid", [])
    assert len(client.calls) == 1
    rows = _journal(path)
    assert len(rows) == 1
    assert rows[0]["step"] == "filters"
    assert rows[0]["outcome"] == "invalid"
