"""Build the film catalog from TMDb.

The script is a one-off maintenance tool. Runtime code never calls TMDb.
The API key is read only from `.env`; it is never printed or committed.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from kino import CATALOG_PATH, GENRES, validate_catalog

SOURCES_PATH = "catalog_sources.json"
TMDB_BASE = "https://api.themoviedb.org/3"
TIMEOUT_SECONDS = 30

GENRE_SYNONYMS: dict[str, str] = {
    "action": "action",
    "adventure": "adventure",
    "animation": "animation",
    "animated": "animation",
    "anime": "animation",
    "biography": "biography",
    "comedy": "comedy",
    "crime": "crime",
    "film-noir": "crime",
    "film noir": "crime",
    "documentary": "documentary",
    "drama": "drama",
    "family": "family",
    "fantasy": "fantasy",
    "history": "history",
    "horror": "horror",
    "music": "musical",
    "musical": "musical",
    "mystery": "mystery",
    "romance": "romance",
    "sci-fi": "science fiction",
    "science fiction": "science fiction",
    "sport": "sport",
    "thriller": "thriller",
    "tv movie": "drama",
    "war": "war",
    "western": "western",
}

COUNTRY_CODES: dict[str, str] = {"KZ": "Казахстан"}
CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def read_env() -> dict[str, str | None]:
    """Read `.env` without exporting anything into the process environment."""
    return dict(dotenv_values(".env"))


def map_genres(names: list[str]) -> list[str]:
    """Map TMDb genre names to the canonical vocabulary, keeping order and cap 4."""
    mapped: list[str] = []
    for name in names:
        canonical = GENRE_SYNONYMS.get(name.strip().lower())
        if canonical and canonical in GENRES and canonical not in mapped:
            mapped.append(canonical)
    return mapped[:4]


def _clean_description(text: str) -> str:
    cleaned = CONTROL_CHARS.sub(" ", text)
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > 500:
        cleaned = cleaned[:500].rsplit(" ", 1)[0].rstrip()
    if len(cleaned) < 20:
        raise ValueError("description is shorter than 20 characters")
    return cleaned


def tmdb_to_film(payload: dict[str, Any], index: int) -> dict[str, Any]:
    """Convert one TMDb movie payload into a catalog film."""
    title = str(payload.get("title") or "").strip()
    release_date = str(payload.get("release_date") or "")
    runtime = payload.get("runtime")
    overview = str(payload.get("overview") or "")

    if not title:
        raise ValueError("title is missing")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", release_date):
        raise ValueError(f"release_date is missing or invalid: {release_date!r}")
    if not isinstance(runtime, int) or runtime <= 0:
        raise ValueError(f"runtime is missing or invalid: {runtime!r}")

    genres = map_genres([str(genre.get("name", "")) for genre in payload.get("genres", [])])
    if not genres:
        raise ValueError("no canonical genre found")

    countries = [
        COUNTRY_CODES.get(str(country.get("iso_3166_1", "")), str(country.get("name", "")))
        for country in payload.get("production_countries", [])
        if country.get("name")
    ]
    if not countries:
        raise ValueError("production_countries is empty")

    languages = [
        str(language.get("english_name") or language.get("name") or "")
        for language in payload.get("spoken_languages", [])
    ]
    languages = [language for language in languages if language]
    if not languages:
        raise ValueError("spoken_languages is empty")

    return {
        "id": f"f-{index:03d}",
        "title": title,
        "year": int(release_date[:4]),
        "minutes": runtime,
        "genres": genres,
        "countries": countries,
        "languages": languages,
        "description": _clean_description(overview),
    }


def _get_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def search_tmdb(title: str, year: int, api_key: str) -> int | None:
    query = urllib.parse.urlencode(
        {"api_key": api_key, "query": title, "year": year, "language": "en-US"}
    )
    payload = _get_json(f"{TMDB_BASE}/search/movie?{query}")
    results = payload.get("results") or []
    if not results:
        return None
    return int(results[0]["id"])


def fetch_tmdb(tmdb_id: int, api_key: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({"api_key": api_key, "language": "en-US"})
    return _get_json(f"{TMDB_BASE}/movie/{tmdb_id}?{query}")


def _wikipedia_url(title: str) -> str:
    return "https://en.wikipedia.org/wiki/Special:Search?search=" + urllib.parse.quote_plus(title)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_catalog(
    existing: list[dict[str, Any]],
    api_key: str,
    *,
    search=search_tmdb,
    fetch=fetch_tmdb,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Rebuild the catalog and provenance from TMDb, preserving existing ids."""
    films: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    retrieved_at = _utc_now()

    for index, old_film in enumerate(existing, start=1):
        tmdb_id = search(old_film["title"], old_film["year"], api_key)
        if tmdb_id is None:
            raise ValueError(f"TMDb has no match for {old_film['title']!r}")
        film = tmdb_to_film(fetch(tmdb_id, api_key), index)
        film["id"] = old_film["id"]
        films.append(film)
        sources.append(
            {
                "id": film["id"],
                "tmdb_id": tmdb_id,
                "retrieved_at": retrieved_at,
                "wikipedia_url": _wikipedia_url(film["title"]),
                "verified_by": "TMDb",
            }
        )
    return films, sources


def main(argv: list[str] | None = None) -> int:
    del argv
    api_key = (read_env().get("TMDB_API_KEY") or "").strip()
    if not api_key:
        print(
            "TMDB_API_KEY is missing from .env; add it to build the catalog.",
            file=sys.stderr,
        )
        return 2

    existing = json.loads(Path(CATALOG_PATH).read_text(encoding="utf-8"))
    try:
        films, sources = build_catalog(existing, api_key)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"catalog build failed: {error}", file=sys.stderr)
        return 1

    problems = validate_catalog(films)
    if problems:
        print("catalog build produced an invalid catalog:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1

    Path(CATALOG_PATH).write_text(
        json.dumps(films, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    Path(SOURCES_PATH).write_text(
        json.dumps(sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(films)} films to {CATALOG_PATH} and {SOURCES_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
