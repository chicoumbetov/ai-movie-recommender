"""Step 14: model and transport failures become outcomes, never crashes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx2
import openai
import pytest

from schemas import Filters


def _request() -> httpx2.Request:
    return httpx2.Request("POST", "https://example.test/v1/chat/completions")


def _connection_error() -> openai.APIConnectionError:
    return openai.APIConnectionError(request=_request())


def _timeout_error() -> openai.APITimeoutError:
    return openai.APITimeoutError(request=_request())


def _status_error(code: int) -> openai.APIStatusError:
    response = httpx2.Response(code, request=_request())
    return openai.APIStatusError("boom", response=response, body=None)


def _run(client: Any, catalog: list[dict[str, Any]], path: Path) -> tuple[str, list]:
    from kino import pick

    return pick(client, "fake-model", "query", catalog, journal_path=path)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (_connection_error(), "no_connection"),
        (_timeout_error(), "no_connection"),
        (_status_error(503), "error_503"),
        (_status_error(429), "error_429"),
    ],
)
def test_transport_errors_in_choice_stage(
    error: BaseException,
    expected: str,
    catalog: list[dict[str, Any]],
    fake_client_factory: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    path = tmp_path / "calls.jsonl"
    client = fake_client_factory([Filters(), error])

    outcome, ids = _run(client, catalog, path)

    assert (outcome, ids) == (expected, [])
    assert capsys.readouterr().out == ""
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["outcome"] == expected
    assert rows[-1]["step"] == "choice"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (_connection_error(), "no_connection"),
        (_timeout_error(), "no_connection"),
        (_status_error(500), "error_500"),
    ],
)
def test_transport_errors_in_filter_stage(
    error: BaseException,
    expected: str,
    catalog: list[dict[str, Any]],
    fake_client_factory: Any,
    tmp_path: Path,
) -> None:
    path = tmp_path / "calls.jsonl"
    client = fake_client_factory([error])

    outcome, ids = _run(client, catalog, path)

    assert (outcome, ids) == (expected, [])
    assert len(client.calls) == 1
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["outcome"] == expected
    assert rows[-1]["step"] == "filters"


def test_refusal_in_choice_stage(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path, capsys: Any
) -> None:
    client = fake_client_factory([Filters(), {"parsed": None, "refusal": "I cannot."}])
    outcome, ids = _run(client, catalog, tmp_path / "calls.jsonl")
    assert (outcome, ids) == ("refusal", [])
    assert capsys.readouterr().out == ""


def test_length_in_choice_stage(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path, capsys: Any
) -> None:
    client = fake_client_factory([Filters(), {"parsed": None, "finish_reason": "length"}])
    outcome, ids = _run(client, catalog, tmp_path / "calls.jsonl")
    assert (outcome, ids) == ("length", [])
    assert capsys.readouterr().out == ""


def test_refusal_in_filter_stage(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path
) -> None:
    client = fake_client_factory([{"parsed": None, "refusal": "I cannot."}])
    outcome, ids = _run(client, catalog, tmp_path / "calls.jsonl")
    assert (outcome, ids) == ("refusal", [])
    assert len(client.calls) == 1


def test_unexpected_exception_is_invalid_and_diagnostic(
    catalog: list[dict[str, Any]],
    fake_client_factory: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    client = fake_client_factory([Filters(), RuntimeError("kaboom")])
    outcome, ids = _run(client, catalog, tmp_path / "calls.jsonl")
    captured = capsys.readouterr()
    assert (outcome, ids) == ("invalid", [])
    assert captured.out == ""
    assert "kaboom" in captured.err
    assert "RuntimeError" in captured.err


def test_journal_is_written_on_every_error(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path
) -> None:
    path = tmp_path / "calls.jsonl"
    client = fake_client_factory([_status_error(502)])
    _run(client, catalog, path)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["request"]["query"] == "query"
    assert "usage" not in rows[0]


def test_empty_choices_in_choice_stage_is_invalid(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path, capsys: Any
) -> None:
    from conftest import FakeParseResult

    empty = FakeParseResult(id="chatcmpl-empty", model="fake-model", usage=None, choices=[])
    client = fake_client_factory([Filters(), empty])

    outcome, ids = _run(client, catalog, tmp_path / "calls.jsonl")

    assert (outcome, ids) == ("invalid", [])
    assert capsys.readouterr().out == ""


def test_empty_choices_in_filter_stage_is_invalid(
    catalog: list[dict[str, Any]], fake_client_factory: Any, tmp_path: Path, capsys: Any
) -> None:
    from conftest import FakeParseResult

    empty = FakeParseResult(id="chatcmpl-empty", model="fake-model", usage=None, choices=[])
    client = fake_client_factory([empty])

    outcome, ids = _run(client, catalog, tmp_path / "calls.jsonl")

    assert (outcome, ids) == ("invalid", [])
    assert capsys.readouterr().out == ""
