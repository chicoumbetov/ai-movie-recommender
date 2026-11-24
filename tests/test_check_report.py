"""Step 20: expectation evaluation and aggregate check report."""

from __future__ import annotations

import check


def test_evaluate_supports_no_match_must_forbid_and_outcome() -> None:
    assert check.evaluate({"no_match": True}, "no_match", [])
    assert not check.evaluate({"no_match": True}, "ok", ["f-001"])
    assert check.evaluate({"must": ["f-001"]}, "ok", ["f-001", "f-002"])
    assert not check.evaluate({"must": ["f-003"]}, "ok", ["f-001"])
    assert check.evaluate({"forbid": ["f-003"]}, "ok", ["f-001"])
    assert not check.evaluate({"must": ["f-001"], "forbid": ["f-002"]}, "ok", ["f-001", "f-002"])
    assert check.evaluate({"outcome": "invalid"}, "invalid", [])
    assert not check.evaluate({"outcome": "invalid"}, "ok", ["f-001"])


def test_run_checks_reports_counts_diagnostics_pass_rate_and_continues() -> None:
    queries = [
        {"query": "first", "expect": {"must": ["f-001"]}},
        {"query": "second", "expect": {"no_match": True}},
        {"query": "third", "expect": {"outcome": "ok"}},
    ]
    called: list[str] = []

    def run_one(query: str) -> tuple[str, list[str | int], list[str | int], int]:
        called.append(query)
        if query == "second":
            return ("no_match", [], [], 0)
        if query == "third":
            return ("invalid", [], ["foreign-9"], 2)
        return ("ok", ["f-001"], [], 0)

    report = check.run_checks(queries, run_one)

    assert called == ["first", "second", "third"]
    assert report.outcome_counts == {"ok": 1, "no_match": 1, "invalid": 1}
    assert report.foreign_ids_caught == ["foreign-9"]
    assert report.filter_violations == 2
    assert report.passed == 2
    assert report.total == 3
    assert report.pass_rate == 2 / 3
    assert report.exit_code == 1
    assert "pass rate: 2/3" in report.format().lower()
    assert "filter violations: 2" in report.format().lower()


def test_run_checks_continues_when_one_query_runner_raises() -> None:
    queries = [
        {"query": "broken", "expect": {"outcome": "ok"}},
        {"query": "after", "expect": {"no_match": True}},
    ]
    called: list[str] = []

    def run_one(query: str) -> tuple[str, list[str | int], list[str | int], int]:
        called.append(query)
        if query == "broken":
            raise RuntimeError("model unavailable")
        return ("no_match", [], [], 0)

    report = check.run_checks(queries, run_one)

    assert called == ["broken", "after"]
    assert report.outcome_counts == {
        "error_RuntimeError": 1,
        "no_match": 1,
    }
    assert report.passed == 1
    assert report.exit_code == 1


def test_run_checks_returns_zero_when_all_expectations_pass() -> None:
    report = check.run_checks(
        [{"query": "q", "expect": {"no_match": True}}],
        lambda _query: ("no_match", [], [], 0),
    )
    assert report.exit_code == 0
