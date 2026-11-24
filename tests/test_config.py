"""Step 1: project configuration baseline."""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pyproject() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as file:
        return tomllib.load(file)


def test_pytest_pythonpath_and_testpaths() -> None:
    config = _pyproject()["tool"]["pytest"]["ini_options"]
    assert config["pythonpath"] == ["."]
    assert config["testpaths"] == ["tests"]


def test_dev_dependencies_include_pytest() -> None:
    groups = _pyproject()["dependency-groups"]
    assert any(item.startswith("pytest") for item in groups["dev"])


def test_requires_python_is_at_least_312() -> None:
    assert _pyproject()["project"]["requires-python"] == ">=3.12"


def test_ruff_targets_python_312() -> None:
    assert _pyproject()["tool"]["ruff"]["target-version"] == "py312"
