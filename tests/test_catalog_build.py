"""Step 6: one-off TMDb catalog builder."""

from __future__ import annotations

from typing import Any

import pytest


def test_genre_synonyms_are_mapped() -> None:
    from scripts.build_catalog import map_genres

    assert map_genres(["Sci-Fi", "Music", "Animated", "Action"]) == [
        "science fiction",
        "musical",
        "animation",
        "action",
    ]


def test_genres_are_deduplicated_and_capped() -> None:
    from scripts.build_catalog import map_genres

    genres = map_genres(["Drama", "drama", "Comedy", "Action", "War", "Horror"])
    assert genres == ["drama", "comedy", "action", "war"]


def test_missing_key_exits_with_code_two(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import scripts.build_catalog as builder

    monkeypatch.setattr(builder, "read_env", lambda: {})
    assert builder.main([]) == 2
    captured = capsys.readouterr()
    assert "TMDB_API_KEY" in captured.err


def test_fake_tmdb_payload_maps_to_catalog_fields() -> None:
    from scripts.build_catalog import tmdb_to_film

    payload: dict[str, Any] = {
        "id": 42,
        "title": "Steppe Story",
        "release_date": "2014-05-01",
        "runtime": 118,
        "overview": "A long enough original description for the fake TMDb payload.",
        "genres": [
            {"id": 18, "name": "Drama"},
            {"id": 10402, "name": "Music"},
        ],
        "production_countries": [
            {"iso_3166_1": "KZ", "name": "Kazakhstan"},
            {"iso_3166_1": "US", "name": "United States of America"},
        ],
        "spoken_languages": [
            {"iso_639_1": "kk", "english_name": "Kazakh", "name": "қазақ"},
            {"iso_639_1": "en", "english_name": "English", "name": "English"},
        ],
    }

    film = tmdb_to_film(payload, 1)

    assert film["id"] == "f-001"
    assert film["title"] == "Steppe Story"
    assert film["year"] == 2014
    assert film["minutes"] == 118
    assert film["genres"] == ["drama", "musical"]
    assert film["countries"] == ["Казахстан", "United States of America"]
    assert film["languages"] == ["Kazakh", "English"]
    assert len(film["description"]) >= 20


def test_payload_without_runtime_is_rejected() -> None:
    from scripts.build_catalog import tmdb_to_film

    payload = {
        "id": 1,
        "title": "No Runtime",
        "release_date": "2020-01-01",
        "runtime": None,
        "overview": "A long enough original description for the fake payload.",
        "genres": [{"name": "Drama"}],
        "production_countries": [{"iso_3166_1": "US", "name": "USA"}],
        "spoken_languages": [{"english_name": "English"}],
    }
    with pytest.raises(ValueError, match="runtime"):
        tmdb_to_film(payload, 1)
