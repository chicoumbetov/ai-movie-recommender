"""Structured model-call journal.

One model call writes one JSON object to `calls.jsonl`. The journal never
contains keys, the full prompt or the full catalog. A write error is reported
as a warning and never crashes the caller.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PRICE: dict[str, tuple[float, float]] = {
    "gpt-6-luna": (0.10, 0.50),
    "gpt-6-astra": (10.00, 50.00),
    "qwen3.5:4b": (0.00, 0.00),
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def log(
    *,
    model: str,
    request: dict[str, Any],
    outcome: str,
    step: str,
    started: float,
    completion: Any = None,
    rejected: list[Any] | None = None,
    path: str | Path | None = None,
) -> None:
    """Append one journal row; never raise on a write failure."""
    row: dict[str, Any] = {
        "time": utc_now(),
        "model": model,
        "request": request,
        "outcome": outcome,
        "step": step,
        "seconds": round(max(0.0, time.time() - started), 3),
    }
    if rejected is not None:
        row["rejected"] = rejected

    usage = getattr(completion, "usage", None) if completion is not None else None
    if usage is not None:
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        price_in, price_out = PRICE.get(model, (0.0, 0.0))
        row["usage"] = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": getattr(usage, "total_tokens", prompt_tokens + completion_tokens),
        }
        row["usd"] = (prompt_tokens * price_in + completion_tokens * price_out) / 1_000_000

    from kino import JOURNAL_PATH

    target = Path(JOURNAL_PATH if path is None else path)
    try:
        with target.open("a", encoding="utf-8") as file:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as error:
        print(f"warning: cannot write journal {target}: {error}", file=sys.stderr)
