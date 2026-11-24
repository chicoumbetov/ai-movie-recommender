"""Step 7: provenance for every catalog film."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_KEYS = {"id", "tmdb_id", "retrieved_at", "wikipedia_url", "verified_by"}


def _sources() -> list[dict]:
    return json.loads((ROOT / "catalog_sources.json").read_text(encoding="utf-8"))


def _films() -> list[dict]:
    return json.loads((ROOT / "data/en/films.json").read_text(encoding="utf-8"))


def test_one_record_per_film() -> None:
    sources = _sources()
    assert len(sources) == 40
    assert [source["id"] for source in sources] == [film["id"] for film in _films()]


def test_records_have_required_keys() -> None:
    for source in _sources():
        assert REQUIRED_KEYS <= source.keys()


def test_tmdb_ids_are_positive_integers_and_unique() -> None:
    ids = [source["tmdb_id"] for source in _sources()]
    assert all(isinstance(value, int) and value > 0 for value in ids)
    assert len(ids) == len(set(ids))


def test_retrieved_at_is_utc_iso8601() -> None:
    for source in _sources():
        value = source["retrieved_at"]
        assert value.endswith("Z")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        assert parsed.utcoffset() is not None
        assert parsed.utcoffset().total_seconds() == 0


def test_wikipedia_urls_are_links() -> None:
    for source in _sources():
        url = source["wikipedia_url"]
        assert url.startswith("https://")
        assert ".wikipedia.org/wiki/" in url


def test_at_least_ten_independent_verifications() -> None:
    independent = [source for source in _sources() if "Wikipedia" in source["verified_by"]]
    assert len(independent) >= 10


def test_every_kazakh_film_has_an_independent_link() -> None:
    films = {film["id"]: film for film in _films()}
    for source in _sources():
        film = films[source["id"]]
        if "Казахстан" in film["countries"]:
            assert "Wikipedia" in source["verified_by"]
            assert ".wikipedia.org/wiki/" in source["wikipedia_url"]
