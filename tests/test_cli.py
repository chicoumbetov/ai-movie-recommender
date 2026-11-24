"""Step 17: kino.py command-line interface."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from schemas import Filters, Pick, Selection

ROOT = Path(__file__).resolve().parents[1]


def _settings(**overrides: str) -> dict[str, str]:
    settings = {
        "api_key": "test-key",
        "base_url": "http://127.0.0.1:1/v1",
        "model": "fake-model",
        "reasoning_effort": "none",
    }
    settings.update(overrides)
    return settings


def _ok() -> Selection:
    return Selection(
        status="ok",
        reason="Fits.",
        picks=[Pick(film_id="kz-001", why="Fits.")],
    )


def test_help_exits_zero(capsys: Any) -> None:
    import kino

    with pytest.raises(SystemExit) as error:
        kino.main(["--help"])
    assert error.value.code == 0
    assert "query" in capsys.readouterr().out.lower()


@pytest.mark.parametrize("query", ["", "   ", "\t\n", "x" * 1001, "bad\x07query"])
def test_bad_query_is_rejected_before_any_call(
    query: str, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    import kino

    def fail(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("pick must not be called for a bad query")

    monkeypatch.setattr(kino, "pick", fail)
    assert kino.main([query]) == 2
    assert capsys.readouterr().err


def test_missing_catalog_is_operational_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: Any
) -> None:
    import kino

    monkeypatch.setattr(kino, "CATALOG_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setattr(kino, "pick", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    assert kino.main(["a film"]) == 2
    assert "catalog" in capsys.readouterr().err.lower()


def test_broken_catalog_is_operational_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: Any
) -> None:
    import kino

    path = tmp_path / "films.json"
    path.write_text("[{", encoding="utf-8")
    monkeypatch.setattr(kino, "CATALOG_PATH", str(path))
    assert kino.main(["a film"]) == 2
    assert "JSON" in capsys.readouterr().err


def test_missing_key_is_a_clear_error(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    import kino

    monkeypatch.setattr(kino, "load_settings", lambda: _settings(api_key=""))
    assert kino.main(["a film"]) == 2
    assert "OPENAI_API_KEY" in capsys.readouterr().err


def test_missing_model_is_a_clear_error(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    import kino

    monkeypatch.setattr(kino, "load_settings", lambda: _settings(model=""))
    assert kino.main(["a film"]) == 2
    assert "MODEL" in capsys.readouterr().err


def test_pick_is_not_called_before_catalog_is_valid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import kino

    monkeypatch.setattr(kino, "CATALOG_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setattr(kino, "load_settings", lambda: _settings())

    def fail(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("pick must not run")

    monkeypatch.setattr(kino, "pick", fail)
    assert kino.main(["a film"]) == 2


@pytest.mark.parametrize(
    ("outcome", "code"),
    [
        ("ok", 0),
        ("no_match", 0),
        ("clarify", 0),
        ("invalid", 1),
        ("refusal", 2),
        ("length", 2),
        ("no_connection", 2),
        ("error_500", 2),
    ],
)
def test_outcome_exit_codes(
    outcome: str,
    code: int,
    monkeypatch: pytest.MonkeyPatch,
    fake_client_factory: Any,
) -> None:
    import kino

    monkeypatch.setattr(kino, "load_settings", lambda: _settings())
    monkeypatch.setattr(kino, "make_client", lambda settings: fake_client_factory([]))
    monkeypatch.setattr(kino, "pick", lambda *args, **kwargs: (outcome, []))
    assert kino.main(["a film"]) == code


def test_success_uses_one_client_and_passes_utf8_query(
    monkeypatch: pytest.MonkeyPatch, fake_client_factory: Any, capsys: Any
) -> None:
    import kino

    client = fake_client_factory([Filters(), _ok()])
    created: list[Any] = []

    def factory(settings: dict[str, str]) -> Any:
        created.append(settings)
        return client

    monkeypatch.setattr(kino, "load_settings", lambda: _settings())
    monkeypatch.setattr(kino, "make_client", factory)

    query = "әлем жоқ, тыныш фильм"
    assert kino.main([query]) == 0
    assert len(created) == 1
    assert query in client.calls[0]["messages"][1]["content"]
    assert "Mongol" in capsys.readouterr().out


def test_make_client_has_no_retries_and_sixty_second_timeout() -> None:
    import kino

    client = kino.make_client(_settings())
    assert client.max_retries == 0
    assert client.timeout == 60


def test_import_has_no_side_effects(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    result = subprocess.run(
        [sys.executable, "-c", "import kino"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == ""
    assert result.stderr == ""


def test_cli_module_runs_help() -> None:
    result = subprocess.run(
        [sys.executable, "kino.py", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "query" in result.stdout.lower()


def test_utf8_catalog_and_query_are_preserved(
    monkeypatch: pytest.MonkeyPatch, fake_client_factory: Any, capsys: Any
) -> None:
    import kino

    client = fake_client_factory([Filters(), _ok()])
    monkeypatch.setattr(kino, "load_settings", lambda: _settings())
    monkeypatch.setattr(kino, "make_client", lambda settings: client)
    assert kino.main(["фильм про Казахстан"]) == 0
    assert "Казахстан" in capsys.readouterr().out


def test_broken_catalog_does_not_leak_json_details(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: Any
) -> None:
    import kino

    path = tmp_path / "films.json"
    path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    monkeypatch.setattr(kino, "CATALOG_PATH", str(path))
    assert kino.main(["a film"]) == 2
    assert "JSON array" in capsys.readouterr().err
