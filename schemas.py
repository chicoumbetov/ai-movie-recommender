"""Pydantic response schemas for the Kinomaniac project.

These schemas define the contract between the code and the model's
response. Using Pydantic models ensures validation of the model output and clear error handling.

The schemas correspond to the `Selection` and `Pick` models. Extra fields are forbidden
to prevent the model from injecting unexpected data.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class Pick(BaseModel):
    """Schema for a single film pick from the model."""

    film_id: str | int
    """Film ID returned by the model. Accepts both string and integer IDs.

    The code normalizes to string for comparison with the catalog but
    returns the original catalog value in `ids`.
    """

    why: str
    """Short qualitative reason in the query language, at most 300 characters,
    on one line. Comes only from the model response."""


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    """Schema for the model's selection response.

    Corresponds to the `Selection` model in SPEC section 8.3.
    Extra fields are forbidden; an extra field produces ValidationError
    and therefore `invalid`.
    """

    status: Literal["ok", "no_match", "clarify"]
    """Selection status: ok (1-3 valid catalog IDs, no duplicates),
    no_match (honestly found nothing), or clarify (one clarifying question)."""

    reason: str
    """Why the selection was made. Required. Stripped, non-empty, at most
    300 characters, single-line."""

    picks: list[Pick]
    """List of 1-3 film picks. Required. Model must never return duplicates
    and never more than three picks."""


# ──────────────────────────────────────────────────────────────
# Legacy compatibility: dynamic Literal for film_id
# ──────────────────────────────────────────────────────────────

# film_id accepts both string and integer IDs.
# A dynamic Literal based on the committed catalog is optional and
# never the only check — the code allowlist is authoritative.
film_id_accepts = str | int
"""Legacy type union for film_id compatibility with both string and
integer catalog IDs."""
