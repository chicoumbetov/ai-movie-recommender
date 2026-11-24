"""Step 12: two-stage pick, happy path and printing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from schemas import Filters, Pick, Selection


def _ok(*picks: tuple[str | int, str]) -> Selection:
    return Selection(
        status="ok",
        reason="Fits.",
        picks=[Pick(film_id=film_id, why=why) for film_id, why in picks],
    )


def test_string_ids_and_model_order(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path
) -> None:
    from kino import pick

    client = fake_client_factory([Filters(), _ok(("f-003", "Bold."), ("f-001", "Quiet."))])
    outcome, ids = pick(
        client, "fake-model", "a film", catalog, journal_path=tmp_path / "calls.jsonl"
    )

    assert outcome == "ok"
    assert ids == ["f-003", "f-001"]
    assert client.calls[0]["response_format"] is Filters
    assert client.calls[1]["response_format"] is Selection


def test_integer_ids(
    int_catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path
) -> None:
    from kino import pick

    client = fake_client_factory([Filters(), _ok((3, "Bold."), (1, "Quiet."))])
    outcome, ids = pick(
        client, "fake-model", "a film", int_catalog, journal_path=tmp_path / "calls.jsonl"
    )

    assert outcome == "ok"
    assert ids == [3, 1]


def test_pick_prints_every_fact_from_the_passed_catalog(
    catalog: list[dict[str, Any]],
    fake_client_factory: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    from kino import pick

    client = fake_client_factory([Filters(), _ok(("f-002", "Funny and warm."))])
    outcome, ids = pick(
        client, "fake-model", "a comedy", catalog, journal_path=tmp_path / "calls.jsonl"
    )
    output = capsys.readouterr().out

    assert outcome == "ok"
    assert ids == ["f-002"]
    film = catalog[1]
    assert film["title"] in output
    assert str(film["year"]) in output
    assert str(film["minutes"]) in output
    assert film["genres"][0] in output
    assert film["countries"][0] in output
    assert film["languages"][0] in output
    assert film["description"] in output
    assert "Why: Funny and warm." in output


def test_pick_does_not_read_the_catalog_file(
    catalog: list[dict[str, Any]],
    fake_client_factory: Any,
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    import kino

    def fail() -> None:
        raise AssertionError("pick must not read data/en/films.json")

    monkeypatch.setattr(kino, "load_catalog", fail)
    client = fake_client_factory([Filters(), _ok(("f-004", "Scary."))])

    outcome, ids = kino.pick(
        client, "fake-model", "a horror", catalog, journal_path=tmp_path / "calls.jsonl"
    )

    assert outcome == "ok"
    assert ids == ["f-004"]


def test_only_filtered_candidates_reach_the_choice_prompt(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path
) -> None:
    from kino import pick

    client = fake_client_factory([Filters(max_minutes=100), _ok(("f-001", "Short."))])
    outcome, ids = pick(
        client, "fake-model", "short films", catalog, journal_path=tmp_path / "calls.jsonl"
    )

    assert outcome == "ok"
    assert ids == ["f-001"]
    choice_prompt = client.calls[1]["messages"][1]["content"]
    assert "f-001" in choice_prompt
    assert "f-003" in choice_prompt
    assert "f-002" not in choice_prompt
    assert "f-004" not in choice_prompt


def test_no_candidates_means_no_choice_call(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path
) -> None:
    from kino import pick

    client = fake_client_factory([Filters(max_minutes=1)])
    outcome, ids = pick(
        client, "fake-model", "one-minute films", catalog, journal_path=tmp_path / "calls.jsonl"
    )

    assert outcome == "no_match"
    assert ids == []
    assert len(client.calls) == 1


def test_journal_has_both_steps(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path
) -> None:
    import json

    from kino import pick

    path = tmp_path / "calls.jsonl"
    client = fake_client_factory([Filters(), _ok(("f-001", "Quiet."))])
    pick(client, "fake-model", "a film", catalog, journal_path=path)

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [row["step"] for row in rows] == ["filters", "choice"]
    assert all(row["model"] == "fake-model" for row in rows)
    assert rows[0]["request"]["query"] == "a film"


def test_filter_prompt_lists_catalog_vocabulary(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path
) -> None:
    from kino import pick

    client = fake_client_factory([Filters(), _ok(("f-001", "Quiet."))])
    pick(client, "fake-model", "a film", catalog, journal_path=tmp_path / "calls.jsonl")

    filter_system = client.calls[0]["messages"][0]["content"]
    for genre in ("action", "comedy", "drama", "horror"):
        assert genre in filter_system
    assert "English" in filter_system
