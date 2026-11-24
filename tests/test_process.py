"""Step 2: process files that keep the workflow honest."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_process_documents_exist() -> None:
    assert (ROOT / "AGENTS.md").is_file()
    assert (ROOT / "PLAN.md").is_file()


def test_agents_lists_required_commands() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for command in (
        "uv sync --frozen",
        "uv run pytest -q",
        "uv run check.py",
        "uv run show.py",
    ):
        assert command in text


def test_agents_lists_prohibitions() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Do not" in text
    assert "Things not to do" in text


def test_plan_uses_unchecked_checkboxes() -> None:
    text = (ROOT / "PLAN.md").read_text(encoding="utf-8")
    assert "- [ ]" in text or "- [x]" in text


def test_opencode_denies_no_verify_and_env_reads() -> None:
    text = (ROOT / "opencode.jsonc").read_text(encoding="utf-8")
    assert "--no-verify" in text
    assert '"deny"' in text
    assert "*.env" in text
    assert "*.env.example" in text
