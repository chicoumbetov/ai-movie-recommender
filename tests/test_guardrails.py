"""Step 15: sanitize model-written why and reason."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from schemas import Filters, Pick, Selection


def _ok(why: str) -> Selection:
    return Selection(status="ok", reason="ok", picks=[Pick(film_id="f-001", why=why)])


def _run(client: Any, catalog: list[dict[str, Any]], path: Path) -> tuple[str, list[str | int]]:
    from kino import pick

    return pick(client, "fake-model", "query", catalog, journal_path=path)


def test_control_characters_are_removed(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path, capsys: Any
) -> None:
    client = fake_client_factory([Filters(), _ok("A\x07B\x00C")])
    outcome, ids = _run(client, catalog, tmp_path / "calls.jsonl")
    assert (outcome, ids) == ("ok", ["f-001"])
    assert "Why: A B C" in capsys.readouterr().out


def test_ansi_sequences_are_removed(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path, capsys: Any
) -> None:
    client = fake_client_factory([Filters(), _ok("\x1b[31mRed\x1b[0m")])
    outcome, ids = _run(client, catalog, tmp_path / "calls.jsonl")
    assert (outcome, ids) == ("ok", ["f-001"])
    output = capsys.readouterr().out
    assert "Why: Red" in output
    assert "\x1b" not in output


def test_multiline_why_becomes_one_line(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path, capsys: Any
) -> None:
    client = fake_client_factory([Filters(), _ok("First line\nSecond\tline")])
    outcome, ids = _run(client, catalog, tmp_path / "calls.jsonl")
    assert (outcome, ids) == ("ok", ["f-001"])
    output = capsys.readouterr().out
    assert "Why: First line Second line" in output


def test_why_longer_than_300_is_invalid(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path, capsys: Any
) -> None:
    client = fake_client_factory([Filters(), _ok("x" * 301)])
    outcome, ids = _run(client, catalog, tmp_path / "calls.jsonl")
    assert (outcome, ids) == ("invalid", [])
    assert capsys.readouterr().out == ""


def test_why_of_exactly_300_is_valid(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path
) -> None:
    client = fake_client_factory([Filters(), _ok("x" * 300)])
    outcome, ids = _run(client, catalog, tmp_path / "calls.jsonl")
    assert (outcome, ids) == ("ok", ["f-001"])


def test_empty_why_is_invalid(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path, capsys: Any
) -> None:
    client = fake_client_factory([Filters(), _ok(" \n\t ")])
    outcome, ids = _run(client, catalog, tmp_path / "calls.jsonl")
    assert (outcome, ids) == ("invalid", [])
    assert capsys.readouterr().out == ""


def test_reason_is_sanitized_for_no_match(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path, capsys: Any
) -> None:
    selection = Selection(status="no_match", reason="\x1b[31mNothing\x1b[0m\nfits", picks=[])
    client = fake_client_factory([Filters(), selection])
    outcome, ids = _run(client, catalog, tmp_path / "calls.jsonl")
    assert (outcome, ids) == ("no_match", [])
    output = capsys.readouterr().out
    assert "Nothing fits" in output
    assert "\x1b" not in output


def test_reason_that_becomes_empty_is_invalid(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path, capsys: Any
) -> None:
    selection = Selection(status="no_match", reason="\x07\x07", picks=[])
    client = fake_client_factory([Filters(), selection])
    outcome, ids = _run(client, catalog, tmp_path / "calls.jsonl")
    assert (outcome, ids) == ("invalid", [])
    assert capsys.readouterr().out == ""


def test_truly_empty_reason_stays_no_match(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path, capsys: Any
) -> None:
    selection = Selection(status="no_match", reason="", picks=[])
    client = fake_client_factory([Filters(), selection])
    outcome, ids = _run(client, catalog, tmp_path / "calls.jsonl")
    assert (outcome, ids) == ("no_match", [])
    assert capsys.readouterr().out.strip()
