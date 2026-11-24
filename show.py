"""Report the model-call journal: outcomes, models, tokens and USD."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from kino import JOURNAL_PATH


def read_rows(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Read valid JSONL rows and silently skip broken lines."""
    target = Path(JOURNAL_PATH if path is None else path)
    if not target.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Count calls by outcome and model, and sum usage and cost."""
    outcomes: Counter[str] = Counter()
    models: Counter[str] = Counter()
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    usd = 0.0

    for row in rows:
        outcomes[str(row.get("outcome", "unknown"))] += 1
        models[str(row.get("model", "unknown"))] += 1
        usage = row.get("usage") or {}
        prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens += int(usage.get("completion_tokens", 0) or 0)
        total_tokens += int(usage.get("total_tokens", 0) or 0)
        usd += float(row.get("usd", 0) or 0)

    return {
        "calls": len(rows),
        "outcomes": dict(sorted(outcomes.items())),
        "models": dict(sorted(models.items())),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "usd": round(usd, 6),
    }


def format_report(report: dict[str, Any]) -> str:
    """Render the report as plain text."""
    if not report["calls"]:
        return "No calls recorded."

    lines = [f"Calls: {report['calls']}", "Outcomes:"]
    lines.extend(f"  {name}: {count}" for name, count in report["outcomes"].items())
    lines.append("Models:")
    lines.extend(f"  {name}: {count}" for name, count in report["models"].items())
    lines.append(
        "Tokens: "
        f"prompt={report['prompt_tokens']}, "
        f"completion={report['completion_tokens']}, "
        f"total={report['total_tokens']}"
    )
    lines.append(f"USD: {report['usd']:.6f}")
    return "\n".join(lines)


def main(path: str | Path | None = None) -> int:
    """Print the journal report and exit successfully even without a journal."""
    print(format_report(aggregate(read_rows(path))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
