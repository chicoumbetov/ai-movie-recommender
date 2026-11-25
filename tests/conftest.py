"""Shared fixtures: tiny catalogs and a deterministic fake OpenAI client."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from types import SimpleNamespace
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def isolated_journal(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep every test away from the committed real-run journal."""
    import utils

    original_log = utils.log

    def isolated_log(*args: Any, path: str | Any = None, **kwargs: Any) -> None:
        original_log(*args, path=tmp_path / "calls.jsonl" if path is None else path, **kwargs)

    monkeypatch.setattr(utils, "log", isolated_log)


def make_film(
    film_id: str | int,
    title: str,
    *,
    year: int = 2000,
    minutes: int = 100,
    genres: list[str] | None = None,
    countries: list[str] | None = None,
    languages: list[str] | None = None,
    description: str = "A short description used by the tests.",
) -> dict[str, Any]:
    """Build one catalog film with valid defaults."""
    return {
        "id": film_id,
        "title": title,
        "year": year,
        "minutes": minutes,
        "genres": genres or ["drama"],
        "countries": countries or ["USA"],
        "languages": languages or ["English"],
        "description": description,
    }


@pytest.fixture
def catalog() -> list[dict[str, Any]]:
    """Four films with string ids."""
    return [
        make_film("f-001", "Alpha", year=1999, minutes=100, genres=["drama"]),
        make_film("f-002", "Beta", year=2005, minutes=120, genres=["comedy"]),
        make_film("f-003", "Gamma", year=2010, minutes=90, genres=["action"]),
        make_film("f-004", "Delta", year=2015, minutes=110, genres=["horror"]),
    ]


@pytest.fixture
def int_catalog() -> list[dict[str, Any]]:
    """Four films with integer ids."""
    return [
        make_film(1, "Alpha", year=1999, minutes=100, genres=["drama"]),
        make_film(2, "Beta", year=2005, minutes=120, genres=["comedy"]),
        make_film(3, "Gamma", year=2010, minutes=90, genres=["action"]),
        make_film(4, "Delta", year=2015, minutes=110, genres=["horror"]),
    ]


class FakeUsage(SimpleNamespace):
    """Minimal stand-in for the SDK usage object."""

    def model_dump(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


class FakeParseResult(SimpleNamespace):
    """Minimal stand-in for the SDK chat completion."""


def _result(
    parsed: Any,
    *,
    finish_reason: str = "stop",
    usage: FakeUsage | None = None,
    refusal: str | None = None,
) -> FakeParseResult:
    usage = usage or FakeUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    message = SimpleNamespace(parsed=parsed, refusal=refusal, content=None)
    return FakeParseResult(
        id="chatcmpl-fake",
        model="fake-model",
        usage=usage,
        choices=[SimpleNamespace(message=message, finish_reason=finish_reason)],
    )


class FakeCompletions:
    """Records calls and replays queued responses or exceptions."""

    def __init__(self, responses: Iterable[Any]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("fake client ran out of responses")
        response = self._responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        if callable(response):
            response = response(kwargs)
        if isinstance(response, FakeParseResult):
            return response
        if isinstance(response, dict) and "parsed" in response:
            return _result(
                response["parsed"],
                finish_reason=response.get("finish_reason", "stop"),
                usage=response.get("usage"),
                refusal=response.get("refusal"),
            )
        return _result(response)


class FakeClient:
    """Minimal client exposing `chat.completions.parse`."""

    def __init__(self, responses: Iterable[Any]) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(responses))

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self.chat.completions.calls


@pytest.fixture
def fake_client_factory() -> Callable[[Iterable[Any]], FakeClient]:
    """Return a factory that builds a fake client from queued responses."""
    return FakeClient
