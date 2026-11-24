"""Pydantic response schemas for the model contract (SPEC.md section 6).

The model returns only catalog ids and short reasons. Extra fields are
forbidden so a schema violation becomes `invalid`, never a silent extra fact.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr

StrictFilmId = StrictStr | StrictInt


class Pick(BaseModel):
    """One selected film: a catalog id and a short reason in the query language."""

    model_config = ConfigDict(extra="forbid", strict=True)

    film_id: StrictFilmId
    why: str


class Selection(BaseModel):
    """The model's choice: status, reason and at most three picks."""

    model_config = ConfigDict(extra="forbid", strict=True)

    status: Literal["ok", "no_match", "clarify"]
    reason: str
    picks: list[Pick]


class Filters(BaseModel):
    """Optional Rare filters. Every field defaults to None; [] equals None."""

    model_config = ConfigDict(extra="forbid", strict=True)

    max_minutes: int | None = None
    year_from: int | None = None
    year_to: int | None = None
    languages: list[str] | None = None
    exclude_genres: list[str] | None = None
    must_genres: list[str] | None = None
