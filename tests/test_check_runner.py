"""Step 21: query loading, pick runner, flags, and CLI exit status."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import check


def test_load_queries_reports_missing_and_invalid_files(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(check.QueryLoadError, match="queries"):
        check.load_queries(missing)

    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    with pytest.raises(check.QueryLoadError, match="JSON"):
        check.load_queries(broken)


def test_run_suite_reuses_pick_and_counts_calls_by_step(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    catalog: list[dict[str, Any]],
) -> None:
    journal = tmp_path / "calls.jsonl"
    client = object()
    seen: list[tuple[Any, str, str, list[dict[str, Any]]]] = []

    def fake_pick(
        received_client: Any,
        model: str,
        query: str,
        films: list[dict[str, Any]],
        *,
        journal_path: str | Path | None = None,
    ) -> tuple[str, list[str | int]]:
        seen.append((received_client, model, query, films))
        assert journal_path == journal
        with journal.open("a", encoding="utf-8") as file:
            file.write(json.dumps({"step": "filters", "outcome": "ok"}) + "\n")
            file.write(json.dumps({"step": "choice", "outcome": "no_match"}) + "\n")
        return ("no_match", [])

    monkeypatch.setattr(check, "pick", fake_pick)
    queries = [{"query": f"q-{index}", "expect": {"no_match": True}} for index in range(2)]

    report = check.run_suite(queries, catalog, client, "chosen-model", runs=3, journal_path=journal)

    assert len(seen) == 6
    assert all(row[0] is client and row[1] == "chosen-model" for row in seen)
    assert report.outcome_counts == {"no_match": 6}
    assert report.step_counts == {"filters": 6, "choice": 6}
    assert report.total == 6
    assert report.exit_code == 0


def test_run_suite_continues_after_pick_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    catalog: list[dict[str, Any]],
) -> None:
    called: list[str] = []

    def fake_pick(
        _client: Any,
        _model: str,
        query: str,
        _films: list[dict[str, Any]],
        *,
        journal_path: str | Path | None = None,
    ) -> tuple[str, list[str | int]]:
        called.append(query)
        if query == "broken":
            raise RuntimeError("pick failed")
        return ("no_match", [])

    monkeypatch.setattr(check, "pick", fake_pick)
    report = check.run_suite(
        [
            {"query": "broken", "expect": {"outcome": "no_match"}},
            {"query": "next", "expect": {"no_match": True}},
        ],
        catalog,
        object(),
        "model",
        journal_path=tmp_path / "calls.jsonl",
    )

    assert called == ["broken", "next"]
    assert report.outcome_counts == {"error_RuntimeError": 1, "no_match": 1}
    assert report.passed == 1
    assert report.exit_code == 1


def test_main_flags_model_runs_and_returns_expectation_exit_code(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    catalog: list[dict[str, Any]],
    capsys: Any,
) -> None:
    settings = {"api_key": "local-placeholder", "model": "default-model"}
    created: list[dict[str, str]] = []
    selected: list[tuple[Any, str, str]] = []
    journal = tmp_path / "calls.jsonl"

    class Client:
        pass

    client = Client()

    def make_client(received: dict[str, str]) -> object:
        created.append(received)
        return client

    def fake_pick(
        received_client: Any,
        model: str,
        query: str,
        _films: list[dict[str, Any]],
        *,
        journal_path: str | Path | None = None,
    ) -> tuple[str, list[str | int]]:
        selected.append((received_client, model, query))
        return ("no_match", [])

    monkeypatch.setattr(
        check,
        "load_queries",
        lambda _path: [{"query": "q", "expect": {"no_match": True}}],
    )
    monkeypatch.setattr(check, "load_catalog", lambda: catalog)
    monkeypatch.setattr(check, "load_settings", lambda: settings)
    monkeypatch.setattr(check, "make_client", make_client)
    monkeypatch.setattr(check, "pick", fake_pick)
    monkeypatch.setattr(check, "JOURNAL_PATH", journal)

    assert check.main(["--model", "override", "--runs", "2"]) == 0
    assert created == [settings]
    assert len(selected) == 2
    assert all(row[0] is client and row[1] == "override" for row in selected)
    assert capsys.readouterr().out.count("Pass rate: 2/2") == 1


def test_main_rejects_nonpositive_runs(capsys: Any) -> None:
    with pytest.raises(SystemExit) as error:
        check.main(["--runs", "0"])
    assert error.value.code == 2


def test_main_returns_nonzero_when_expectation_fails(
    monkeypatch: pytest.MonkeyPatch,
    catalog: list[dict[str, Any]],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        check,
        "load_queries",
        lambda _path: [{"query": "q", "expect": {"no_match": True}}],
    )
    monkeypatch.setattr(check, "load_catalog", lambda: catalog)
    monkeypatch.setattr(
        check,
        "load_settings",
        lambda: {"api_key": "local-placeholder", "model": "default"},
    )
    monkeypatch.setattr(check, "make_client", lambda _settings: object())
    monkeypatch.setattr(check, "pick", lambda *_args, **_kwargs: ("invalid", []))
    monkeypatch.setattr(check, "JOURNAL_PATH", tmp_path / "calls.jsonl")

    assert check.main([]) == 1
