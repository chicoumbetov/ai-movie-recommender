"""Step 8: strict response schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_valid_ok_selection() -> None:
    from schemas import Pick, Selection

    selection = Selection(
        status="ok",
        reason="Matches the mood.",
        picks=[Pick(film_id="f-001", why="Warm and quiet.")],
    )
    assert selection.status == "ok"
    assert selection.picks[0].film_id == "f-001"


def test_no_match_and_clarify_are_valid() -> None:
    from schemas import Selection

    assert Selection(status="no_match", reason="Nothing fits.", picks=[]).status == "no_match"
    assert Selection(status="clarify", reason="Which era?", picks=[]).status == "clarify"


def test_extra_field_is_forbidden() -> None:
    from schemas import Pick, Selection

    with pytest.raises(ValidationError):
        Selection(status="ok", reason="x", picks=[], extra="nope")
    with pytest.raises(ValidationError):
        Pick(film_id="f-001", why="x", extra="nope")


def test_film_id_accepts_string_and_integer() -> None:
    from schemas import Pick

    assert Pick(film_id="f-001", why="x").film_id == "f-001"
    assert Pick(film_id=1, why="x").film_id == 1
    assert Pick(film_id="1", why="x").film_id == "1"


@pytest.mark.parametrize("bad_id", [None, 1.5, 1.0, True])
def test_film_id_rejects_null_float_and_bool(bad_id: object) -> None:
    from schemas import Pick

    with pytest.raises(ValidationError):
        Pick(film_id=bad_id, why="x")


def test_missing_fields_are_rejected() -> None:
    from schemas import Pick, Selection

    with pytest.raises(ValidationError):
        Selection(status="ok", picks=[])
    with pytest.raises(ValidationError):
        Selection(status="ok", reason="x")
    with pytest.raises(ValidationError):
        Pick(film_id="f-001")


def test_unknown_status_is_rejected() -> None:
    from schemas import Selection

    with pytest.raises(ValidationError):
        Selection(status="maybe", reason="x", picks=[])


def test_filters_default_to_none() -> None:
    from schemas import Filters

    filters = Filters()
    assert filters.max_minutes is None
    assert filters.year_from is None
    assert filters.year_to is None
    assert filters.languages is None
    assert filters.exclude_genres is None
    assert filters.must_genres is None
