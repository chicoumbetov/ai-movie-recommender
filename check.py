"""Expectation evaluation and reporting for the query check runner."""

from __future__ import annotations

import json
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kino import JOURNAL_PATH, CatalogError, load_catalog, load_settings, make_client, pick

QUERY_PATH = Path("queries.json")
RunOne = Callable[[str], tuple[str, list[str | int], list[str | int], int]]


class QueryLoadError(ValueError):
    """Raised when the evaluation query file cannot be read or validated."""


def load_queries(path: str | Path = QUERY_PATH) -> list[dict[str, Any]]:
    """Load the query array and report file or JSON problems with its path."""
    target = Path(path)
    try:
        raw = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise QueryLoadError(f"cannot read queries file {target}: {error}") from error
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise QueryLoadError(f"invalid JSON in queries file {target}: {error}") from error
    if not isinstance(value, list):
        raise QueryLoadError(f"queries file {target} must contain a JSON array")
    for index, item in enumerate(value, start=1):
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("query"), str)
            or not item["query"].strip()
            or not isinstance(item.get("expect"), dict)
        ):
            raise QueryLoadError(f"queries file {target}: item {index} needs query and expect")
    return value


def evaluate(expect: Mapping[str, Any], outcome: str, ids: Sequence[str | int]) -> bool:
    """Apply the single pass rule defined in SPEC.md to one result."""
    normalized_ids = {str(film_id) for film_id in ids}

    if "outcome" in expect and outcome != expect["outcome"]:
        return False
    if expect.get("no_match") is True and (outcome != "no_match" or ids):
        return False

    must = expect.get("must", [])
    forbid = expect.get("forbid", [])
    if must and not any(str(film_id) in normalized_ids for film_id in must):
        return False
    if any(str(film_id) in normalized_ids for film_id in forbid):
        return False

    if "outcome" in expect or expect.get("no_match") is True or must or forbid:
        return True
    return outcome == "no_match" and not ids


@dataclass(frozen=True)
class CheckReport:
    outcome_counts: dict[str, int]
    foreign_ids_caught: list[str | int]
    filter_violations: int
    passed: int
    total: int
    failures: list[str]
    step_counts: dict[str, int] = field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 1.0

    @property
    def exit_code(self) -> int:
        return 0 if not self.failures else 1

    def format(self) -> str:
        lines = ["Outcome counts:"]
        lines.extend(
            f"  {outcome}: {count}" for outcome, count in sorted(self.outcome_counts.items())
        )
        lines.append(f"Foreign IDs caught: {self.foreign_ids_caught}")
        lines.append(f"Filter violations: {self.filter_violations}")
        lines.append("Model calls by step:")
        lines.extend(f"  {step}: {count}" for step, count in sorted(self.step_counts.items()))
        lines.append(f"Pass rate: {self.passed}/{self.total} ({self.pass_rate:.1%})")
        if self.failures:
            lines.append("Failures:")
            lines.extend(f"  {failure}" for failure in self.failures)
        return "\n".join(lines)


def run_checks(
    queries: Sequence[Mapping[str, Any]],
    run_one: RunOne,
    *,
    step_counts: Mapping[str, int] | None = None,
) -> CheckReport:
    """Run each query and aggregate results; a single runner error cannot stop later queries.

    `run_one` delegates selection to `kino.pick` and returns its outcome and IDs,
    plus diagnostics collected from the call journal.
    """
    counts: Counter[str] = Counter()
    foreign_ids: list[str | int] = []
    filter_violations = 0
    failures: list[str] = []

    for index, item in enumerate(queries, start=1):
        query = str(item["query"])
        expect = item["expect"]
        try:
            outcome, ids, rejected, violations = run_one(query)
        except Exception as error:  # Keep evaluating the rest of the query set.
            outcome, ids, rejected, violations = (
                f"error_{type(error).__name__}",
                [],
                [],
                0,
            )
        counts[outcome] += 1
        foreign_ids.extend(rejected)
        filter_violations += violations
        if not evaluate(expect, outcome, ids):
            failures.append(
                f"query {index}: {query!r} expected {dict(expect)!r}, "
                f"got {outcome} {ids!r}"
            )

    passed = len(queries) - len(failures)
    return CheckReport(
        outcome_counts=dict(counts),
        foreign_ids_caught=foreign_ids,
        filter_violations=filter_violations,
        passed=passed,
        total=len(queries),
        failures=failures,
        step_counts=dict(step_counts or {}),
    )


def _journal_rows(path: str | Path) -> list[dict[str, Any]]:
    """Read valid call rows; malformed lines do not change per-step totals."""
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def run_suite(
    queries: Sequence[Mapping[str, Any]],
    films: list[dict[str, Any]],
    client: Any,
    model: str,
    *,
    runs: int = 1,
    journal_path: str | Path = JOURNAL_PATH,
) -> CheckReport:
    """Run the query set through `pick`, repeating the complete set if requested."""
    if runs < 1:
        raise ValueError("runs must be at least 1")

    known_ids = {str(film["id"]) for film in films}
    steps: Counter[str] = Counter()

    def run_one(query: str) -> tuple[str, list[str | int], list[str | int], int]:
        before = _journal_rows(journal_path)
        try:
            outcome, ids = pick(
                client,
                model,
                query,
                films,
                journal_path=journal_path,
            )
        finally:
            after = _journal_rows(journal_path)
            new_rows = after[len(before) :]
            for row in new_rows:
                step = row.get("step")
                if step in {"filters", "choice"}:
                    steps[step] += 1

        rejected: list[str | int] = []
        filter_violations = 0
        for row in new_rows:
            values = row.get("rejected", [])
            if not isinstance(values, list):
                continue
            for film_id in values:
                if not isinstance(film_id, (str, int)) or isinstance(film_id, bool):
                    continue
                if str(film_id) in known_ids:
                    filter_violations += 1
                else:
                    rejected.append(film_id)
        return (outcome, ids, rejected, filter_violations)

    expanded = [query for _ in range(runs) for query in queries]
    return run_checks(expanded, run_one, step_counts=steps)


def build_parser() -> Any:
    import argparse

    parser = argparse.ArgumentParser(
        prog="check.py",
        description="Run the evaluation queries against the film catalog.",
    )
    parser.add_argument("--model", help="model name (defaults to MODEL from .env)")
    parser.add_argument("--runs", type=int, default=1, help="number of full query-set runs")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for repeated model checks."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.runs < 1:
        parser.error("--runs must be at least 1")

    try:
        queries = load_queries(QUERY_PATH)
        films = load_catalog()
    except (QueryLoadError, CatalogError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    settings = load_settings()
    if not settings.get("api_key"):
        print("error: OPENAI_API_KEY is missing from .env", file=sys.stderr)
        return 2
    model = args.model or settings.get("model", "")
    if not model:
        print("error: MODEL is missing from .env or --model", file=sys.stderr)
        return 2

    try:
        client = make_client(settings)
        report = run_suite(queries, films, client, model, runs=args.runs)
    except Exception as error:  # Operational setup failures still have a clear CLI result.
        print(f"error: cannot run checks: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    print(report.format())
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
