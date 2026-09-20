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
