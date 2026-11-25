"""The configured reasoning effort is forwarded to local compatible APIs."""

from __future__ import annotations

from typing import Any

from kino import _call_model
from schemas import Filters


def test_call_model_forwards_configured_reasoning_effort(
    fake_client_factory: Any, monkeypatch: Any
) -> None:
    monkeypatch.setenv("REASONING_EFFORT", "none")
    client = fake_client_factory([Filters()])

    completion, outcome = _call_model(
        client,
        "qwen3.5:4b",
        [{"role": "user", "content": "query"}],
        Filters,
    )

    assert completion is not None
    assert outcome == "ok"
    assert client.calls[0]["extra_body"] == {"reasoning_effort": "none"}
