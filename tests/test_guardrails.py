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


def _ok_for(film_id: str, why: str) -> Selection:
    return Selection(status="ok", reason="ok", picks=[Pick(film_id=film_id, why=why)])


def _run_query(
    client: Any,
    catalog: list[dict[str, Any]],
    path: Path,
    query: str = "query",
) -> tuple[str, list[str | int]]:
    from kino import pick

    return pick(client, "fake-model", query, catalog, journal_path=path)


def test_year_claim_must_match_the_film(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path
) -> None:
    client = fake_client_factory([Filters(), _ok_for("f-001", "A 2001 film.")])
    assert _run(client, catalog, tmp_path / "calls.jsonl") == ("invalid", [])

    client = fake_client_factory([Filters(), _ok_for("f-001", "A 1999 film.")])
    assert _run(client, catalog, tmp_path / "calls.jsonl") == ("ok", ["f-001"])


def test_year_in_query_is_allowed(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path
) -> None:
    client = fake_client_factory([Filters(), _ok_for("f-001", "A 2001 film.")])
    outcome, ids = _run_query(client, catalog, tmp_path / "calls.jsonl", "films from 2001")
    assert (outcome, ids) == ("ok", ["f-001"])


def test_minutes_claim_must_match_the_film(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path
) -> None:
    client = fake_client_factory([Filters(), _ok_for("f-001", "Runs 120 minutes.")])
    assert _run(client, catalog, tmp_path / "calls.jsonl") == ("invalid", [])

    client = fake_client_factory([Filters(), _ok_for("f-001", "Runs 100 minutes.")])
    assert _run(client, catalog, tmp_path / "calls.jsonl") == ("ok", ["f-001"])


def test_minutes_in_query_are_allowed(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path
) -> None:
    client = fake_client_factory([Filters(), _ok_for("f-001", "Runs 120 minutes.")])
    outcome, ids = _run_query(client, catalog, tmp_path / "calls.jsonl", "about 120 minutes")
    assert (outcome, ids) == ("ok", ["f-001"])


def test_foreign_title_is_forbidden(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path
) -> None:
    client = fake_client_factory([Filters(), _ok_for("f-001", "Better than Beta.")])
    assert _run(client, catalog, tmp_path / "calls.jsonl") == ("invalid", [])


def test_foreign_title_in_query_is_allowed(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path
) -> None:
    client = fake_client_factory([Filters(), _ok_for("f-001", "Like Beta but quieter.")])
    outcome, ids = _run_query(client, catalog, tmp_path / "calls.jsonl", "I liked Beta")
    assert (outcome, ids) == ("ok", ["f-001"])


def test_own_title_is_allowed(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path
) -> None:
    client = fake_client_factory([Filters(), _ok_for("f-001", "Alpha is quiet.")])
    assert _run(client, catalog, tmp_path / "calls.jsonl") == ("ok", ["f-001"])


def test_title_word_boundary(catalog: list[dict[str, Any]]) -> None:
    from kino import verify_why

    films = [
        {"id": "f-001", "title": "Alpha", "year": 2000, "minutes": 100},
        {"id": "f-002", "title": "Drive", "year": 2011, "minutes": 100},
    ]
    assert verify_why("A Driver story.", films[0], films, "query")
    assert not verify_why("A Drive story.", films[0], films, "query")


def test_russian_why_for_english_query_is_allowed(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path
) -> None:
    client = fake_client_factory([Filters(), _ok_for("f-001", "Тихий фильм без спецэффектов.")])
    assert _run(client, catalog, tmp_path / "calls.jsonl") == ("ok", ["f-001"])


def test_year_outside_the_guard_range_is_ignored(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path
) -> None:
    client = fake_client_factory([Filters(), _ok_for("f-001", "A story from 1800.")])
    assert _run(client, catalog, tmp_path / "calls.jsonl") == ("ok", ["f-001"])
