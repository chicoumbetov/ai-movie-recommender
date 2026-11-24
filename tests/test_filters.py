"""Step 10: Rare filter logic."""

from __future__ import annotations

from typing import Any

from conftest import make_film


def test_no_conditions_returns_whole_catalog(catalog: list[dict[str, Any]]) -> None:
    from kino import apply_filters
    from schemas import Filters

    assert apply_filters(catalog, Filters()) == catalog


def test_empty_lists_equal_none(catalog: list[dict[str, Any]]) -> None:
    from kino import apply_filters
    from schemas import Filters

    filters = Filters(
        languages=[],
        exclude_genres=[],
        must_genres=[],
        max_minutes=None,
        year_from=None,
        year_to=None,
    )
    assert apply_filters(catalog, filters) == catalog


def test_max_minutes_is_inclusive(catalog: list[dict[str, Any]]) -> None:
    from kino import apply_filters
    from schemas import Filters

    ids = [film["id"] for film in apply_filters(catalog, Filters(max_minutes=100))]
    assert ids == ["f-001", "f-003"]


def test_year_range_is_inclusive(catalog: list[dict[str, Any]]) -> None:
    from kino import apply_filters
    from schemas import Filters

    ids = [film["id"] for film in apply_filters(catalog, Filters(year_from=2005, year_to=2010))]
    assert ids == ["f-002", "f-003"]


def test_languages_require_at_least_one_match() -> None:
    from kino import apply_filters
    from schemas import Filters

    films = [
        make_film("f-001", "Alpha", languages=["English", "French"]),
        make_film("f-002", "Beta", languages=["Japanese"]),
        make_film("f-003", "Gamma", languages=["French"]),
    ]
    ids = [film["id"] for film in apply_filters(films, Filters(languages=["french"]))]
    assert ids == ["f-001", "f-003"]


def test_exclude_genres(catalog: list[dict[str, Any]]) -> None:
    from kino import apply_filters
    from schemas import Filters

    ids = [
        film["id"] for film in apply_filters(catalog, Filters(exclude_genres=["comedy", "action"]))
    ]
    assert ids == ["f-001", "f-004"]


def test_must_genres_requires_all(catalog: list[dict[str, Any]]) -> None:
    from kino import apply_filters
    from schemas import Filters

    films = catalog + [make_film("f-005", "Epsilon", genres=["drama", "comedy"])]
    ids = [film["id"] for film in apply_filters(films, Filters(must_genres=["drama"]))]
    assert ids == ["f-001", "f-005"]
    ids = [film["id"] for film in apply_filters(films, Filters(must_genres=["drama", "comedy"]))]
    assert ids == ["f-005"]


def test_combined_filters(catalog: list[dict[str, Any]]) -> None:
    from kino import apply_filters
    from schemas import Filters

    filters = Filters(
        max_minutes=130,
        year_from=2000,
        exclude_genres=["horror"],
        must_genres=["comedy"],
    )
    ids = [film["id"] for film in apply_filters(catalog, filters)]
    assert ids == ["f-002"]


def test_violates_filters(catalog: list[dict[str, Any]]) -> None:
    from kino import violates_filters
    from schemas import Filters

    alpha, beta, gamma, delta = catalog
    assert not violates_filters(alpha, Filters(max_minutes=100))
    assert violates_filters(beta, Filters(max_minutes=100))
    assert violates_filters(alpha, Filters(year_from=2000))
    assert not violates_filters(beta, Filters(year_to=2005))
    assert violates_filters(gamma, Filters(exclude_genres=["action"]))
    assert violates_filters(delta, Filters(must_genres=["drama"]))
    assert violates_filters(delta, Filters(languages=["French"]))


def test_catalog_vocabulary(catalog: list[dict[str, Any]]) -> None:
    from kino import catalog_vocabulary

    vocabulary = catalog_vocabulary(catalog)
    assert vocabulary["genres"] == ["action", "comedy", "drama", "horror"]
    assert vocabulary["languages"] == ["English"]
