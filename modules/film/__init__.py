"""Film catalog model matching SPEC.md section 4.2.

Pydantic model for film objects in films.json. Uses extra="forbid"
for strict validation, matching AGENTS.md 3.4 architecture.

Used by: pick(), CLI validation, catalog loading.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, validator

CanonicalGenre = Literal[
    "action", "adventure", "animation", "biography", "comedy",
    "crime", "documentary", "drama", "family", "fantasy",
    "history", "horror", "musical", "mystery", "romance",
    "science fiction", "sport", "thriller", "war", "western",
]


class Film(BaseModel, extra="forbid"):
    """Catalog film object matching SPEC.md section 4.2.

    Attributes:
        id: Unique identifier. String or integer, same type across
            entire catalog. Non-empty if string.
        title: Non-empty English or international title.
        year: Release year, 1888 through current year.
        minutes: Runtime in minutes, 1-600.
        genres: 1-4 values from canonical 20-genre vocabulary.
        countries: Non-empty list. "Казахстан" for Kazakhstan films,
            other countries in English.
        languages: Non-empty list of English language names.
        description: 1-2 original sentences, 20-500 characters,
            no control characters, no copied synopsis.
    """

    id: str | int
    """Unique film identifier. Must be same type across entire catalog."""

    title: str = Field(..., min_length=1, description="English or international title")
    """Non-empty title."""

    year: int = Field(..., ge=1888, le=2099, description="Release year")
    """Year 1888 through current year (validated to 2099 max)."""

    minutes: int = Field(..., ge=1, le=600, description="Runtime in minutes")
    """Runtime 1-600 minutes."""

    genres: list[CanonicalGenre] = Field(
        ..., min_items=1, max_items=4,
        description="1-4 canonical genres",
    )
    """1-4 values from canonical vocabulary."""

    countries: list[str] = Field(
        ..., min_items=1, description="Production countries",
    )
    """Non-empty list. "Казахстан" for Kazakhstan."""

    languages: list[str] = Field(
        ..., min_items=1, description="Spoken languages",
    )
    """Non-empty list of English language names."""

    description: str = Field(
        ..., min_length=20, max_length=500,
        description="1-2 original sentences",
    )
    """1-2 original sentences, 20-500 chars, no control chars."""

    # ── Validators ──────────────────────────────────────────────

    @validator("description")
    def no_control_chars(cls, v):
        """Description must not contain ASCII control characters."""
        import re
        if re.search(r"[\x00-\x1f\x7f]", v):
            raise ValueError("no control chars")
        return v

    @validator("description")
    def single_line(cls, v):
        """Description must be single line (no newlines)."""
        return v.replace("\n", "").replace("\r", "")

    @validator("genres")
    def genres_stripped(cls, v):
        """Genres stripped of surrounding whitespace."""
        return [g.strip() for g in v]

    @validator("countries")
    def countries_must_be_non_empty_strings(cls, v):
        """Countries must be non-empty strings."""
        for c in v:
            if not c or not c.strip():
                raise ValueError("countries must contain non-empty strings")
        return [c.strip() for c in v]

    @validator("languages")
    def languages_must_be_non_empty_strings(cls, v):
        """Languages must be non-empty strings."""
        for language in v:
            if not language or not language.strip():
                raise ValueError("languages must contain non-empty strings")
        return [language.strip() for language in v]
