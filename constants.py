"""Code constants for the Kinomaniac (Movie bluff) project.

These constants are the single source of truth for configuration values,
paths, and limits used throughout the codebase. Defining them here
avoids duplication in SPEC.md and ensures consistency.
"""

# ──────────────────────────────────────────────────────────────
# Code constants (from SPEC)
# ──────────────────────────────────────────────────────────────

MAX_PICKS: int = 3
"""Maximum number of films per answer."""

MAX_QUERY_CHARS: int = 1000
"""Maximum input query length in characters."""

MAX_WHY_CHARS: int = 300
"""Maximum length of model's `why` reason in characters."""

REQUEST_TIMEOUT_SECONDS: int = 60
"""Timeout for one model call in seconds."""

MAX_CANDIDATES: int = 30
"""Optional cap for filtered candidates."""

CATALOG_PATH: str = "data/en/films.json"
"""Catalog file path."""

JOURNAL_PATH: str = "calls.jsonl"
"""Call journal file path."""

STATE_PATH: str = "state.json"
"""Bot state file path."""

MAX_CLARIFY_TURNS: int = 1
"""Clarify loop guard maximum."""

TELEGRAM_MAX_MESSAGE_CHARS = 4096
"""Telegram message limit"""
