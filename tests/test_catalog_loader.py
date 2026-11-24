"""Step 5: catalog loader with complete diagnostics."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_missing_file_raises_catalog_error(tmp_path: Path) -> None:
    import kino

    with pytest.raises(kino.CatalogError, match="not found"):
        kino.load_catalog(tmp_path / "missing.json")


def test_broken_json_raises_catalog_error(tmp_path: Path) -> None:
    import kino

    path = tmp_path / "films.json"
    path.write_text("[{", encoding="utf-8")
    with pytest.raises(kino.CatalogError, match="JSON"):
        kino.load_catalog(path)


def test_broken_utf8_raises_catalog_error(tmp_path: Path) -> None:
    import kino

    path = tmp_path / "films.json"
    path.write_bytes(b"\xff\xfe\x00\x00")
    with pytest.raises(kino.CatalogError, match="UTF-8"):
        kino.load_catalog(path)


def test_all_problems_are_reported_together(tmp_path: Path) -> None:
    import kino

    films = json.loads(Path("data/en/films.json").read_text(encoding="utf-8"))
    films = films[:39]
    films[0]["genres"] = ["not-a-genre"]
    path = tmp_path / "films.json"
    path.write_text(json.dumps(films), encoding="utf-8")

    with pytest.raises(kino.CatalogError) as error:
        kino.load_catalog(path)

    message = str(error.value)
    assert "40 to 60" in message
    assert "unknown genre" in message


def test_valid_file_is_loaded(tmp_path: Path) -> None:
    import kino

    source = Path("data/en/films.json")
    path = tmp_path / "films.json"
    path.write_bytes(source.read_bytes())

    films = kino.load_catalog(path)

    assert len(films) == 40
    assert films[0]["id"] == "kz-001"


def test_default_path_is_used(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import kino

    path = tmp_path / "films.json"
    path.write_bytes(Path("data/en/films.json").read_bytes())
    monkeypatch.setattr(kino, "CATALOG_PATH", str(path))

    assert kino.load_catalog()[0]["title"] == "Mongol: The Rise of Genghis Khan"
