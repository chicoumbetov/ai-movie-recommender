"""The Russian catalog mirrors the English facts with Russian labels."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

GENRES = {
    "action": "боевик",
    "adventure": "приключения",
    "animation": "анимация",
    "biography": "биография",
    "comedy": "комедия",
    "crime": "криминал",
    "drama": "драма",
    "fantasy": "фэнтези",
    "history": "история",
    "horror": "ужасы",
    "musical": "мюзикл",
    "romance": "романтика",
    "science fiction": "фантастика",
    "thriller": "триллер",
    "war": "война",
    "western": "вестерн",
}

COUNTRIES = {
    "Australia": "Австралия",
    "Brazil": "Бразилия",
    "China": "Китай",
    "France": "Франция",
    "Germany": "Германия",
    "Italy": "Италия",
    "Japan": "Япония",
    "Mexico": "Мексика",
    "New Zealand": "Новая Зеландия",
    "Poland": "Польша",
    "Russia": "Россия",
    "South Korea": "Южная Корея",
    "Spain": "Испания",
    "USA": "США",
    "United Kingdom": "Великобритания",
    "Казахстан": "Казахстан",
}

LANGUAGES = {
    "English": "английский",
    "French": "французский",
    "German": "немецкий",
    "Italian": "итальянский",
    "Japanese": "японский",
    "Kazakh": "казахский",
    "Korean": "корейский",
    "Kyrgyz": "киргизский",
    "Mandarin": "китайский",
    "Mongolian": "монгольский",
    "Portuguese": "португальский",
    "Russian": "русский",
    "Spanish": "испанский",
}


def _films(language: str) -> list[dict[str, Any]]:
    path = ROOT / "data" / language / "films.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _translate(
    values: list[str],
    mapping: dict[str, str],
    *,
    film_id: str,
    field: str,
) -> list[str]:
    unknown = [value for value in values if value not in mapping]
    assert not unknown, f"{film_id}: no Russian label for {field}: {unknown}"
    return [mapping[value] for value in values]


def test_ids_and_order_match() -> None:
    english = _films("en")
    russian = _films("ru")
    assert [film["id"] for film in english] == [film["id"] for film in russian]


def test_years_and_runtimes_match() -> None:
    english = _films("en")
    russian = {film["id"]: film for film in _films("ru")}
    for film in english:
        mirror = russian[film["id"]]
        assert mirror["year"] == film["year"], film["id"]
        assert mirror["minutes"] == film["minutes"], film["id"]


def test_genres_countries_and_languages_are_russian_translations() -> None:
    english = _films("en")
    russian = {film["id"]: film for film in _films("ru")}
    for film in english:
        mirror = russian[film["id"]]
        for field, mapping in (
            ("genres", GENRES),
            ("countries", COUNTRIES),
            ("languages", LANGUAGES),
        ):
            assert mirror[field] == _translate(
                film[field], mapping, film_id=film["id"], field=field
            ), (film["id"], field)


def test_kazakhstan_token_is_not_translated() -> None:
    films = _films("ru")
    assert sum("Казахстан" in film["countries"] for film in films) >= 5
    for film in films:
        assert "Kazakhstan" not in film["countries"], film["id"]
