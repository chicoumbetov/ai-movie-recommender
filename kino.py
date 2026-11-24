"""Kinomaniac: catalog validation and the selection entry point.

The module is deliberately import-safe: it defines constants and functions but
never reads a file, prints or creates a client at import time.
"""

from __future__ import annotations

import re
from typing import Any

GENRES: tuple[str, ...] = (
    "action",
    "adventure",
    "animation",
    "biography",
    "comedy",
    "crime",
    "documentary",
    "drama",
    "family",
    "fantasy",
    "history",
    "horror",
    "musical",
    "mystery",
    "romance",
    "science fiction",
    "sport",
    "thriller",
    "war",
    "western",
)

MAX_PICKS: int = 3
MAX_QUERY_CHARS: int = 1000
MAX_WHY_CHARS: int = 300
REQUEST_TIMEOUT_SECONDS: int = 60
CATALOG_PATH: str = "data/en/films.json"
JOURNAL_PATH: str = "calls.jsonl"

FILM_FIELDS: frozenset[str] = frozenset(
    {"id", "title", "year", "minutes", "genres", "countries", "languages", "description"}
)
FORBIDDEN_TAGS: tuple[str, ...] = ("<catalog>", "</catalog>", "<query>", "</query>")
CONTROL_CHARS: re.Pattern[str] = re.compile(r"[\x00-\x1f\x7f]")
MIN_FILMS: int = 40
MAX_FILMS: int = 60
MIN_YEAR: int = 1888
MAX_YEAR: int = 2099
MIN_MINUTES: int = 1
MAX_MINUTES: int = 600
MIN_DESCRIPTION: int = 20
MAX_DESCRIPTION: int = 500
KAZAKHSTAN: str = "Казахстан"
MIN_KAZAKHSTAN: int = 5


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _check_text(value: str, where: str, problems: list[str]) -> None:
    if CONTROL_CHARS.search(value):
        problems.append(f"{where}: contains an ASCII control character")
    for tag in FORBIDDEN_TAGS:
        if tag in value:
            problems.append(f"{where}: contains the forbidden prompt tag {tag!r}")


def validate_catalog(films: Any) -> list[str]:
    """Return every catalog problem; an empty list means the catalog is valid."""
    problems: list[str] = []
    if not isinstance(films, list):
        return ["catalog must be a JSON array"]

    if not MIN_FILMS <= len(films) <= MAX_FILMS:
        problems.append(f"catalog must contain {MIN_FILMS} to {MAX_FILMS} films, got {len(films)}")

    id_types: set[type] = set()
    seen_ids: set[str | int] = set()
    kazakhstan_count = 0

    for index, film in enumerate(films):
        where = f"film {index}"
        if not isinstance(film, dict):
            problems.append(f"{where}: must be a JSON object")
            continue

        missing = FILM_FIELDS - film.keys()
        if missing:
            problems.append(f"{where}: missing fields: {', '.join(sorted(missing))}")

        film_id = film.get("id")
        if not isinstance(film_id, (str, int)) or isinstance(film_id, bool):
            problems.append(f"{where}: id must be a non-empty string or an integer")
        elif isinstance(film_id, str) and not film_id:
            problems.append(f"{where}: id must not be empty")
        else:
            id_types.add(type(film_id))
            if film_id in seen_ids:
                problems.append(f"{where}: duplicate id {film_id!r}")
            seen_ids.add(film_id)
            if isinstance(film_id, str):
                _check_text(film_id, f"{where}.id", problems)

        title = film.get("title")
        if not isinstance(title, str) or not title.strip():
            problems.append(f"{where}: title must be a non-empty string")
        else:
            _check_text(title, f"{where}.title", problems)

        year = film.get("year")
        if not _is_int(year) or not MIN_YEAR <= year <= MAX_YEAR:
            problems.append(f"{where}: year must be an integer in {MIN_YEAR}..{MAX_YEAR}")

        minutes = film.get("minutes")
        if not _is_int(minutes) or not MIN_MINUTES <= minutes <= MAX_MINUTES:
            problems.append(f"{where}: minutes must be an integer in {MIN_MINUTES}..{MAX_MINUTES}")

        genres = film.get("genres")
        if not isinstance(genres, list) or not 1 <= len(genres) <= 4:
            problems.append(f"{where}: genres must be a list of 1 to 4 values")
        else:
            for genre in genres:
                if not isinstance(genre, str) or genre not in GENRES:
                    problems.append(f"{where}: unknown genre {genre!r}")
                elif isinstance(genre, str):
                    _check_text(genre, f"{where}.genres", problems)

        countries = film.get("countries")
        if not isinstance(countries, list) or not countries:
            problems.append(f"{where}: countries must be a non-empty list")
        else:
            for country in countries:
                if not isinstance(country, str) or not country.strip():
                    problems.append(f"{where}: country must be a non-empty string")
                else:
                    _check_text(country, f"{where}.countries", problems)
            if KAZAKHSTAN in countries:
                kazakhstan_count += 1

        languages = film.get("languages")
        if not isinstance(languages, list) or not languages:
            problems.append(f"{where}: languages must be a non-empty list")
        else:
            for language in languages:
                if not isinstance(language, str) or not language.strip():
                    problems.append(f"{where}: language must be a non-empty string")
                else:
                    _check_text(language, f"{where}.languages", problems)

        description = film.get("description")
        if not isinstance(description, str) or not (
            MIN_DESCRIPTION <= len(description) <= MAX_DESCRIPTION
        ):
            problems.append(
                f"{where}: description must be {MIN_DESCRIPTION} to {MAX_DESCRIPTION} characters"
            )
        else:
            _check_text(description, f"{where}.description", problems)

    if len(id_types) > 1:
        problems.append("catalog: id type must be the same for every film")
    if kazakhstan_count < MIN_KAZAKHSTAN:
        problems.append(
            f"catalog: at least {MIN_KAZAKHSTAN} films must list the exact country "
            f"token {KAZAKHSTAN!r}, got {kazakhstan_count}"
        )

    return problems
