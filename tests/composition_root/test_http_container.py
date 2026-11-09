import pytest
from fastapi.testclient import TestClient

from application.errors import EngineNotConfigured
from composition_root.containers import http_container
from infrastructure.config.server_config import ServerConfig
from infrastructure.config.stt_config import SttConfig


def test_openai_engine_wires_an_app_that_answers_health():
    container = http_container.new_http_container(
        ServerConfig.from_env({}), SttConfig.from_env({"OPENAI_API_KEY": "sk-test"})
    )

    body = TestClient(container.app).get("/health").json()
    assert body["status"] == "success" and body["action"] == "health_check"
    assert container.stt.is_available() is True


def test_openai_engine_without_a_key_fails_at_startup():
    with pytest.raises(EngineNotConfigured, match="OPENAI_API_KEY"):
        http_container.new_http_container(ServerConfig.from_env({}), SttConfig.from_env({}))


def test_any_other_engine_name_selects_the_local_engine(monkeypatch):
    loaded: list[str] = []

    class FakeWhisperModel:
        def __init__(self, name: str, **kwargs: object) -> None:
            loaded.append(name)

    monkeypatch.setattr(
        "infrastructure.outbound.local_whisper.local_whisper_transcription.WhisperModel",
        FakeWhisperModel,
    )

    container = http_container.new_http_container(
        ServerConfig.from_env({}), SttConfig.from_env({"STT_ENGINE": "local"})
    )

    assert loaded == ["small.en"]
    assert container.stt.is_available() is True


def test_the_local_settings_reach_the_main_model_and_the_gate(monkeypatch):
    built: list[tuple[str, dict[str, object]]] = []

    class FakeWhisperModel:
        def __init__(self, name: str, **kwargs: object) -> None:
            built.append((name, kwargs))

    monkeypatch.setattr(
        "infrastructure.outbound.local_whisper.local_whisper_transcription.WhisperModel",
        FakeWhisperModel,
    )

    http_container.new_http_container(
        ServerConfig.from_env({}),
        SttConfig.from_env(
            {
                "STT_ENGINE": "local",
                "STT_MODEL": "small",
                "STT_THREADS": "4",
                "STT_COMPUTE_TYPE": "float32",
                "STT_GATE_ENABLED": "1",
                "STT_GATE_MODEL": "base.en",
            }
        ),
    )

    # the main model and the gate: their own model names, the threads and the compute type shared
    assert built == [
        ("small", {"device": "cpu", "compute_type": "float32", "cpu_threads": 4}),
        ("base.en", {"device": "cpu", "compute_type": "float32", "cpu_threads": 4}),
    ]


def test_with_no_local_setting_the_main_model_and_the_gate_are_built_as_before(monkeypatch):
    built: list[tuple[str, dict[str, object]]] = []

    class FakeWhisperModel:
        def __init__(self, name: str, **kwargs: object) -> None:
            built.append((name, kwargs))

    monkeypatch.setattr(
        "infrastructure.outbound.local_whisper.local_whisper_transcription.WhisperModel",
        FakeWhisperModel,
    )

    http_container.new_http_container(
        ServerConfig.from_env({}),
        SttConfig.from_env({"STT_ENGINE": "local", "STT_GATE_ENABLED": "1"}),
    )

    assert built == [
        ("small.en", {"device": "cpu", "compute_type": "int8", "cpu_threads": 2}),
        ("base", {"device": "cpu", "compute_type": "int8", "cpu_threads": 2}),
    ]
