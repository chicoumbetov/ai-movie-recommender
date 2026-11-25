"""Step 3: repository hygiene and environment template."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_ENV_KEYS = {
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "MODEL",
    "REASONING_EFFORT",
    "TMDB_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_API_BASE",
    "BOT_STATE_PATH",
    "TELEGRAM_POLL_TIMEOUT_SECONDS",
    "TELEGRAM_MAX_MESSAGE_CHARS",
    "MAX_CLARIFY_TURNS",
    "CHECK_RUNS",
}


def _git(*args: str, check: bool = True) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
    ).stdout


def _is_git_worktree() -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def _gitignore() -> list[str]:
    return [
        line.strip()
        for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def test_calls_journal_is_not_ignored() -> None:
    assert "calls.jsonl" not in _gitignore()
    if _is_git_worktree():
        assert not _git("check-ignore", "calls.jsonl", check=False).strip()


def test_state_and_qa_journals_are_ignored() -> None:
    ignored = _gitignore()
    for name in ("state.json", "state.json.tmp", "qa_calls.jsonl"):
        assert name in ignored
        if _is_git_worktree():
            assert _git("check-ignore", name).strip() == name


def test_env_example_lists_all_keys() -> None:
    keys = set()
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            keys.add(line.split("=", 1)[0].strip())
    assert REQUIRED_ENV_KEYS <= keys


def test_env_example_has_no_real_looking_secrets() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert not re.search(r"sk-[A-Za-z0-9]{10,}", text)
    assert not re.search(r"\b\d{8,}:[A-Za-z0-9_-]{20,}\b", text)
    assert not re.search(r"[A-Za-z0-9]{32,}", text)


def test_env_file_is_not_tracked() -> None:
    if _is_git_worktree():
        tracked = set(_git("ls-files").splitlines())
        assert ".env" not in tracked
        assert ".env.example" in tracked
    else:
        assert not (ROOT / ".env").exists()
        assert (ROOT / ".env.example").is_file()
