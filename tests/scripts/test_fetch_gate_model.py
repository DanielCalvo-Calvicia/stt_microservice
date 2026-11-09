"""``scripts/fetch_gate_model.py``, the deploy tool's ``prepare`` step: which models it fetches and how it fails.

No network, no model and no ``.env``: the script is loaded from its path, ``load_dotenv`` is replaced by a
no-op (the service folder may hold a real ``.env`` that no test may read), and ``faster_whisper`` is a fake.
"""

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "fetch_gate_model.py"

SETTINGS = (
    "STT_ENGINE",
    "STT_GATE_ENABLED",
    "STT_GATE_MODEL",
    "STT_GATE_PROMPT",
    "STT_MODEL",
    "STT_THREADS",
    "STT_COMPUTE_TYPE",
)

# what the settings default to
CPU_INT8 = {"device": "cpu", "compute_type": "int8", "cpu_threads": 2}


@pytest.fixture
def script(monkeypatch):
    """The script as a module: no ``.env`` loaded, none of the service's settings in the environment."""
    for name in SETTINGS:
        monkeypatch.delenv(name, raising=False)
    spec = importlib.util.spec_from_file_location("fetch_gate_model_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "load_dotenv", lambda *args, **kwargs: None)
    return module


def _fake_faster_whisper(
    monkeypatch, errors: dict[str, Exception] | None = None
) -> list[tuple[tuple, dict]]:
    """A ``faster_whisper`` whose ``WhisperModel`` remembers how it was called.

    ``errors`` maps a model name to the exception loading that model raises.
    """
    calls: list[tuple[tuple, dict[str, Any]]] = []

    def whisper_model(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))
        if errors and args[0] in errors:
            raise errors[args[0]]

    fake = types.SimpleNamespace(WhisperModel=whisper_model)
    monkeypatch.setitem(sys.modules, "faster_whisper", fake)
    return calls


def _loaded_names(calls: list[tuple[tuple, dict]]) -> list[str]:
    return [args[0] for args, _ in calls]


# --- nothing to fetch ---


def test_with_the_openai_engine_and_the_gate_off_nothing_is_fetched_and_the_exit_code_is_0(
    script, monkeypatch, capsys
):
    calls = _fake_faster_whisper(monkeypatch)

    assert script.main() == 0

    assert "No local model needed" in capsys.readouterr().out
    assert calls == []


@pytest.mark.parametrize("engine", ["openai", "OpenAI"])
def test_the_openai_engine_never_fetches_the_main_model(script, monkeypatch, engine):
    monkeypatch.setenv("STT_ENGINE", engine)
    monkeypatch.setenv("STT_MODEL", "small")
    calls = _fake_faster_whisper(monkeypatch)

    assert script.main() == 0

    assert calls == []


# --- the gate ---


def test_with_the_gate_on_it_loads_the_gate_model_like_the_service_and_says_it_is_ready(
    script, monkeypatch, capsys
):
    monkeypatch.setenv("STT_GATE_ENABLED", "1")
    monkeypatch.setenv("STT_GATE_MODEL", "base.en")
    calls = _fake_faster_whisper(monkeypatch)

    assert script.main() == 0

    assert calls == [(("base.en",), CPU_INT8)]
    out = capsys.readouterr().out
    assert "Loading the gate model base.en" in out and "Gate model base.en is ready" in out


def test_the_gate_model_defaults_to_base(script, monkeypatch):
    monkeypatch.setenv("STT_GATE_ENABLED", "1")
    calls = _fake_faster_whisper(monkeypatch)

    assert script.main() == 0

    assert _loaded_names(calls) == ["base"]


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " On "])
def test_the_gate_is_on_for_the_same_spellings_as_the_service(script, monkeypatch, value):
    monkeypatch.setenv("STT_GATE_ENABLED", value)
    calls = _fake_faster_whisper(monkeypatch)

    assert script.main() == 0

    assert len(calls) == 1


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "2"])
def test_the_gate_is_off_for_anything_else(script, monkeypatch, value):
    monkeypatch.setenv("STT_GATE_ENABLED", value)
    calls = _fake_faster_whisper(monkeypatch)

    assert script.main() == 0

    assert calls == []


# --- the main model (T-01.3.2) ---


def test_the_local_engine_fetches_the_main_model_with_the_configured_model_threads_and_compute_type(
    script, monkeypatch, capsys
):
    monkeypatch.setenv("STT_ENGINE", "local")
    monkeypatch.setenv("STT_MODEL", "small")
    monkeypatch.setenv("STT_THREADS", "4")
    monkeypatch.setenv("STT_COMPUTE_TYPE", "Float32")
    calls = _fake_faster_whisper(monkeypatch)

    assert script.main() == 0

    assert calls == [(("small",), {"device": "cpu", "compute_type": "float32", "cpu_threads": 4})]
    out = capsys.readouterr().out
    assert "Loading the main model small" in out and "Main model small is ready" in out


def test_the_main_model_defaults_to_small_en_and_zero_threads_is_passed_on(script, monkeypatch):
    monkeypatch.setenv("STT_ENGINE", "local")
    calls = _fake_faster_whisper(monkeypatch)
    assert script.main() == 0
    assert calls == [(("small.en",), CPU_INT8)]

    monkeypatch.setenv("STT_THREADS", "0")
    calls = _fake_faster_whisper(monkeypatch)
    assert script.main() == 0
    assert calls == [(("small.en",), {**CPU_INT8, "cpu_threads": 0})]


@pytest.mark.parametrize("engine", ["local", "LOCAL", "faster-whisper"])
def test_any_engine_name_other_than_openai_is_the_local_engine_as_in_the_service(
    script, monkeypatch, engine
):
    monkeypatch.setenv("STT_ENGINE", engine)
    calls = _fake_faster_whisper(monkeypatch)

    assert script.main() == 0

    assert _loaded_names(calls) == ["small.en"]


def test_the_local_engine_with_the_gate_on_fetches_both_models_main_first_with_shared_settings(
    script, monkeypatch
):
    monkeypatch.setenv("STT_ENGINE", "local")
    monkeypatch.setenv("STT_GATE_ENABLED", "1")
    monkeypatch.setenv("STT_THREADS", "3")
    monkeypatch.setenv("STT_COMPUTE_TYPE", "int8_float16")
    calls = _fake_faster_whisper(monkeypatch)

    assert script.main() == 0

    shared = {"device": "cpu", "compute_type": "int8_float16", "cpu_threads": 3}
    assert calls == [(("small.en",), shared), (("base",), shared)]


def test_a_name_needed_twice_is_loaded_once(script, monkeypatch, capsys):
    monkeypatch.setenv("STT_ENGINE", "local")
    monkeypatch.setenv("STT_GATE_ENABLED", "1")
    monkeypatch.setenv("STT_MODEL", "base.en")
    monkeypatch.setenv("STT_GATE_MODEL", "base.en")
    calls = _fake_faster_whisper(monkeypatch)

    assert script.main() == 0

    assert _loaded_names(calls) == ["base.en"]
    assert "Main and gate model base.en is ready" in capsys.readouterr().out


# --- failures: a warning for the deploy tool, never a crash ---


def test_a_model_that_cannot_be_loaded_is_exit_code_1_with_the_reason_on_stderr(
    script, monkeypatch, capsys
):
    monkeypatch.setenv("STT_GATE_ENABLED", "1")
    monkeypatch.setenv("STT_GATE_MODEL", "tiny.en-typo")
    _fake_faster_whisper(monkeypatch, errors={"tiny.en-typo": OSError("no network")})

    assert script.main() == 1

    captured = capsys.readouterr()
    assert "Could not load the gate model tiny.en-typo: no network" in captured.err
    assert "is ready" not in captured.out


def test_when_the_main_model_fails_the_gate_is_still_tried_and_the_exit_code_is_1(
    script, monkeypatch, capsys
):
    monkeypatch.setenv("STT_ENGINE", "local")
    monkeypatch.setenv("STT_GATE_ENABLED", "1")
    calls = _fake_faster_whisper(monkeypatch, errors={"small.en": OSError("disk full")})

    assert script.main() == 1

    assert _loaded_names(calls) == ["small.en", "base"]
    captured = capsys.readouterr()
    assert "Could not load the main model small.en: disk full" in captured.err
    assert "Gate model base is ready" in captured.out and "Main model" not in captured.out


def test_when_the_gate_fails_the_main_model_was_already_fetched(script, monkeypatch, capsys):
    monkeypatch.setenv("STT_ENGINE", "local")
    monkeypatch.setenv("STT_GATE_ENABLED", "1")
    calls = _fake_faster_whisper(monkeypatch, errors={"base": OSError("no network")})

    assert script.main() == 1

    assert _loaded_names(calls) == ["small.en", "base"]
    captured = capsys.readouterr()
    assert "Main model small.en is ready" in captured.out
    assert "Could not load the gate model base: no network" in captured.err


def test_a_bad_setting_is_exit_code_1_with_the_reason_not_a_traceback(script, monkeypatch, capsys):
    monkeypatch.setenv("STT_ENGINE", "local")
    monkeypatch.setenv("STT_THREADS", "many")
    calls = _fake_faster_whisper(monkeypatch)

    assert script.main() == 1

    assert calls == []
    assert "STT_THREADS" in capsys.readouterr().err
