"""Step 13: invalid model answers never leak a film."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from schemas import Filters, Pick, Selection


def _selection(status: str, *picks: tuple[str | int, str]) -> Selection:
    return Selection(
        status=status,
        reason="Reason.",
        picks=[Pick(film_id=film_id, why=why) for film_id, why in picks],
    )


def _pick(
    client: Any,
    catalog: list[dict[str, Any]],
    path: Path,
) -> tuple[str, list[str | int]]:
    from kino import pick

    return pick(client, "fake-model", "query", catalog, journal_path=path)


def test_foreign_id_is_invalid_rejected_and_silent(
    catalog: list[dict[str, Any]],
    fake_client_factory: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    path = tmp_path / "calls.jsonl"
    client = fake_client_factory([Filters(), _selection("ok", ("f-999", "Ghost."))])

    outcome, ids = _pick(client, catalog, path)

    assert outcome == "invalid"
    assert ids == []
    assert capsys.readouterr().out == ""
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["outcome"] == "invalid"
    assert rows[-1]["rejected"] == ["f-999"]


def test_duplicate_is_invalid(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path, capsys: Any
) -> None:
    client = fake_client_factory([Filters(), _selection("ok", ("f-001", "A."), ("f-001", "B."))])
    outcome, ids = _pick(client, catalog, tmp_path / "calls.jsonl")
    assert (outcome, ids) == ("invalid", [])
    assert capsys.readouterr().out == ""


def test_more_than_three_is_invalid(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path, capsys: Any
) -> None:
    picks = [(film["id"], "Why.") for film in catalog]
    client = fake_client_factory([Filters(), _selection("ok", *picks)])
    outcome, ids = _pick(client, catalog, tmp_path / "calls.jsonl")
    assert (outcome, ids) == ("invalid", [])
    assert capsys.readouterr().out == ""


def test_ok_with_empty_picks_is_invalid(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path, capsys: Any
) -> None:
    client = fake_client_factory([Filters(), _selection("ok")])
    outcome, ids = _pick(client, catalog, tmp_path / "calls.jsonl")
    assert (outcome, ids) == ("invalid", [])
    assert capsys.readouterr().out == ""


def test_no_match_with_picks_is_invalid(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path, capsys: Any
) -> None:
    client = fake_client_factory([Filters(), _selection("no_match", ("f-001", "A."))])
    outcome, ids = _pick(client, catalog, tmp_path / "calls.jsonl")
    assert (outcome, ids) == ("invalid", [])
    assert capsys.readouterr().out == ""


def test_no_match_prints_reason_or_generic(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path, capsys: Any
) -> None:
    client = fake_client_factory([Filters(), _selection("no_match")])
    outcome, ids = _pick(client, catalog, tmp_path / "calls.jsonl")
    assert (outcome, ids) == ("no_match", [])
    assert "Reason." in capsys.readouterr().out

    empty_reason = Selection(status="no_match", reason="", picks=[])
    client = fake_client_factory([Filters(), empty_reason])
    outcome, ids = _pick(client, catalog, tmp_path / "calls.jsonl")
    assert (outcome, ids) == ("no_match", [])
    assert capsys.readouterr().out.strip()


def test_clarify_with_empty_picks_is_valid(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path, capsys: Any
) -> None:
    selection = Selection(status="clarify", reason="Which decade?", picks=[])
    client = fake_client_factory([Filters(), selection])
    outcome, ids = _pick(client, catalog, tmp_path / "calls.jsonl")
    assert (outcome, ids) == ("clarify", [])
    assert "Which decade?" in capsys.readouterr().out


def test_validation_error_is_invalid(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path, capsys: Any
) -> None:
    try:
        Selection(status="bad", reason="x", picks=[])
    except ValidationError as error:
        validation_error = error

    client = fake_client_factory([Filters(), validation_error])
    outcome, ids = _pick(client, catalog, tmp_path / "calls.jsonl")
    assert (outcome, ids) == ("invalid", [])
    assert capsys.readouterr().out == ""


def test_ids_are_trimmed(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path
) -> None:
    client = fake_client_factory([Filters(), _selection("ok", (" f-002 ", "A."))])
    outcome, ids = _pick(client, catalog, tmp_path / "calls.jsonl")
    assert (outcome, ids) == ("ok", ["f-002"])


def test_numeric_string_matches_integer_id(
    int_catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path
) -> None:
    client = fake_client_factory([Filters(), _selection("ok", ("3", "A."))])
    outcome, ids = _pick(client, int_catalog, tmp_path / "calls.jsonl")
    assert (outcome, ids) == ("ok", [3])


def test_integer_and_numeric_string_are_duplicates(
    int_catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path
) -> None:
    client = fake_client_factory([Filters(), _selection("ok", (1, "A."), ("1", "B."))])
    outcome, ids = _pick(client, int_catalog, tmp_path / "calls.jsonl")
    assert (outcome, ids) == ("invalid", [])


@pytest.mark.parametrize("status", ["invalid", "no_match", "clarify"])
def test_ids_are_empty_for_every_non_ok_outcome(
    status: str,
    catalog: list[dict[str, Any]],
    fake_client_factory: Any,
    tmp_path: Path,
) -> None:
    if status == "invalid":
        selection = _selection("ok", ("f-999", "Ghost."))
    else:
        selection = Selection(status=status, reason="Reason.", picks=[])
    client = fake_client_factory([Filters(), selection])
    outcome, ids = _pick(client, catalog, tmp_path / "calls.jsonl")
    if status == "invalid":
        assert outcome == "invalid"
    else:
        assert outcome == status
    assert ids == []
