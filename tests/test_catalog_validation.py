"""Step 4: constants and full catalog validation."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]


def real_catalog() -> list[dict[str, Any]]:
    return json.loads((ROOT / "data/en/films.json").read_text(encoding="utf-8"))


def test_real_catalog_is_valid() -> None:
    import kino

    assert kino.validate_catalog(real_catalog()) == []


def test_constants_match_spec() -> None:
    import kino

    assert len(kino.GENRES) == 20
    assert "science fiction" in kino.GENRES
    assert kino.MAX_PICKS == 3
    assert kino.MAX_QUERY_CHARS == 1000
    assert kino.MAX_WHY_CHARS == 300
    assert kino.REQUEST_TIMEOUT_SECONDS == 60
    assert kino.CATALOG_PATH == "data/en/films.json"
    assert kino.JOURNAL_PATH == "calls.jsonl"


def test_size_bounds() -> None:
    import kino

    films = real_catalog()
    assert kino.validate_catalog(films[:39])
    assert kino.validate_catalog(films + films[:21])


def test_required_fields_and_types() -> None:
    import kino

    films = real_catalog()
    broken = copy.deepcopy(films)
    del broken[0]["title"]
    broken[1]["year"] = "1999"
    broken[2]["minutes"] = 0
    broken[3]["genres"] = []
    broken[4]["countries"] = []
    broken[5]["languages"] = []
    broken[6]["description"] = "too short"
    problems = kino.validate_catalog(broken)
    assert len(problems) >= 6


def test_unique_and_single_type_ids() -> None:
    import kino

    films = real_catalog()
    duplicate = copy.deepcopy(films)
    duplicate[1]["id"] = duplicate[0]["id"]
    assert any("duplicate" in p.lower() for p in kino.validate_catalog(duplicate))

    mixed = copy.deepcopy(films)
    mixed[0]["id"] = 1
    assert any("type" in p.lower() for p in kino.validate_catalog(mixed))


def test_year_and_minutes_bounds() -> None:
    import kino

    films = real_catalog()
    broken = copy.deepcopy(films)
    broken[0]["year"] = 1887
    broken[1]["minutes"] = 0
    assert kino.validate_catalog(broken)


def test_genre_dictionary_and_count() -> None:
    import kino

    films = real_catalog()
    broken = copy.deepcopy(films)
    broken[0]["genres"] = ["unknown-genre"]
    broken[1]["genres"] = ["drama"] * 5
    problems = kino.validate_catalog(broken)
    assert len(problems) >= 2


def test_kazakhstan_token_is_required() -> None:
    import kino

    films = copy.deepcopy(real_catalog())
    for film in films:
        film["countries"] = [c for c in film["countries"] if c != "Казахстан"]
    problems = kino.validate_catalog(films)
    assert any("Казахстан" in p for p in problems)


def test_tags_and_control_characters_are_forbidden() -> None:
    import kino

    films = real_catalog()
    broken = copy.deepcopy(films)
    broken[0]["title"] = "Bad <каталог> title"
    broken[1]["description"] = "Has a control char \x07 inside a long enough text."
    problems = kino.validate_catalog(broken)
    assert len(problems) >= 2


def test_description_bounds() -> None:
    import kino

    films = real_catalog()
    broken = copy.deepcopy(films)
    broken[0]["description"] = "x" * 19
    broken[1]["description"] = "x" * 501
    problems = kino.validate_catalog(broken)
    assert len(problems) >= 2


def test_import_has_no_side_effects(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    result = subprocess.run(
        [sys.executable, "-c", "import kino"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == ""
    assert result.stderr == ""


def test_validate_accepts_integer_ids(int_catalog: list[dict[str, Any]]) -> None:
    import kino

    # Four films are below the catalog minimum, but id typing is still checked.
    problems = kino.validate_catalog(int_catalog)
    assert any("40" in p for p in problems)
    assert not any("id type" in p.lower() for p in problems)


@pytest.mark.parametrize("bad", [[], [{}]])
def test_structural_failures(bad: list[dict[str, Any]]) -> None:
    import kino

    assert kino.validate_catalog(bad)
