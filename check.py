"""Expectation evaluation and reporting for the query check runner."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

RunOne = Callable[[str], tuple[str, list[str | int], list[str | int], int]]


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
        lines.append(f"Pass rate: {self.passed}/{self.total} ({self.pass_rate:.1%})")
        if self.failures:
            lines.append("Failures:")
            lines.extend(f"  {failure}" for failure in self.failures)
        return "\n".join(lines)


def run_checks(queries: Sequence[Mapping[str, Any]], run_one: RunOne) -> CheckReport:
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
    )
