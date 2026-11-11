"""The two engines against fake models / clients; no network and no model download."""

import asyncio
import os
import types
from typing import Any

import httpx
import numpy as np
import openai
import pytest
from shared_logging.testing import capture

from application.errors import TranscriptionFailed
from infrastructure.outbound.local_whisper.local_whisper_transcription import (
    LocalWhisperTranscription,
    _pcm_to_whisper_input,
)
from infrastructure.outbound.openai_whisper import openai_whisper_transcription as openai_module
from infrastructure.outbound.openai_whisper.openai_whisper_transcription import (
    OpenAIWhisperTranscription,
)


def _pcm_chunk(value: int, samples: int = 1024) -> bytes:
    return np.full(samples, value, dtype=np.int16).tobytes()


class RecordingModel:
    """Stands in for faster-whisper's model: remembers how it was asked, answers a fixed text."""

    def __init__(self) -> None:
        self.kwargs: dict[str, Any] = {}
        self.samples: Any = None

    def transcribe(self, audio_data: Any, **kwargs: Any):
        self.samples = audio_data
        self.kwargs = kwargs

        class Segment:
            text = " final local text"

        return [Segment()], None


def _local_engine(monkeypatch, model: RecordingModel, **kwargs: Any) -> LocalWhisperTranscription:
    monkeypatch.setattr(
        "infrastructure.outbound.local_whisper.local_whisper_transcription.WhisperModel",
        lambda *args, **options: model,
    )
    return LocalWhisperTranscription(**kwargs)


def test_pcm_is_resampled_to_16k_for_whisper():
    samples = _pcm_to_whisper_input(np.zeros(8000, dtype=np.int16).tobytes(), 8000)
    assert samples.dtype == np.float32 and len(samples) == 16000


def test_pcm_already_at_16k_is_only_scaled():
    samples = _pcm_to_whisper_input(_pcm_chunk(16384, 100), 16000)
    assert len(samples) == 100 and float(samples[0]) == 0.5


def test_local_engine_transcribes_one_utterance_and_is_available(monkeypatch):
    model = RecordingModel()
    engine = _local_engine(monkeypatch, model, language="es")

    text = asyncio.run(engine.transcribe_batch(_pcm_chunk(1000), 16000))

    assert text == " final local text"
    assert model.kwargs["language"] == "es"
    assert engine.is_available() is True


def test_local_engine_sends_no_prompt_unless_it_has_one_and_uses_beam_5_by_default(monkeypatch):
    model = RecordingModel()
    asyncio.run(_local_engine(monkeypatch, model).transcribe_batch(_pcm_chunk(1000), 16000))

    assert "initial_prompt" not in model.kwargs and model.kwargs["beam_size"] == 5


def test_local_engine_passes_its_prompt_and_beam_size_to_the_model(monkeypatch):
    model = RecordingModel()
    engine = _local_engine(monkeypatch, model, initial_prompt="Oblivion 306", beam_size=1)

    asyncio.run(engine.transcribe_batch(_pcm_chunk(1000), 16000))

    assert model.kwargs["initial_prompt"] == "Oblivion 306" and model.kwargs["beam_size"] == 1


def test_openai_engine_availability_follows_the_api_key():
    assert OpenAIWhisperTranscription(api_key="k").is_available() is True
    assert OpenAIWhisperTranscription(api_key="").is_available() is False


def _fake_openai(monkeypatch, calls: list[dict[str, Any]]) -> None:
    class FakeTranscriptions:
        def create(self, **kwargs: Any) -> str:
            calls.append({**kwargs, "riff": kwargs["file"].read(4)})
            return "  hola  "

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            self.audio = types.SimpleNamespace(transcriptions=FakeTranscriptions())

    monkeypatch.setattr(openai_module, "OpenAI", FakeClient)


def test_openai_batch_calls_the_api_with_a_wav_and_cleans_up(monkeypatch):
    calls: list[dict[str, Any]] = []
    _fake_openai(monkeypatch, calls)
    removed: list[str] = []
    real_remove = openai_module._remove_temp_file
    monkeypatch.setattr(
        openai_module, "_remove_temp_file", lambda path: (removed.append(path), real_remove(path))
    )

    text = asyncio.run(OpenAIWhisperTranscription("k", "es").transcribe_batch(_pcm_chunk(5), 16000))

    assert text == "hola"
    assert calls[0]["language"] == "es" and calls[0]["model"] == "whisper-1"
    assert calls[0]["riff"] == b"RIFF"
    assert len(removed) == 1
    assert not os.path.exists(removed[0])


def test_openai_batch_sends_the_prompt_only_when_there_is_one(monkeypatch):
    calls: list[dict[str, Any]] = []
    _fake_openai(monkeypatch, calls)

    asyncio.run(OpenAIWhisperTranscription("k", "en").transcribe_batch(_pcm_chunk(5), 16000))
    asyncio.run(
        OpenAIWhisperTranscription("k", "en", prompt="Oblivion 306").transcribe_batch(
            _pcm_chunk(5), 16000
        )
    )

    assert "prompt" not in calls[0]
    assert calls[1]["prompt"] == "Oblivion 306"


def test_openai_batch_writes_the_wav_at_the_rate_of_the_utterance(monkeypatch):
    seen: list[int] = []
    _fake_openai(monkeypatch, [])
    real_write = openai_module._write_wav_file

    def spying_write(raw: bytes, rate: int) -> str:
        seen.append(rate)
        return real_write(raw, rate)

    monkeypatch.setattr(openai_module, "_write_wav_file", spying_write)

    asyncio.run(OpenAIWhisperTranscription("k").transcribe_batch(_pcm_chunk(5), 44100))

    assert seen == [44100]


# --- the OpenAI engine when the API refuses: no text of the library, so no part of a key ---

_REQUEST = httpx.Request("POST", "https://api.openai.com/v1/audio/transcriptions")
_LIBRARY_TEXT = (
    "Error code: 401 - Incorrect API key provided: sk-fake-*********************0000. "
    "You can find your API key at https://platform.openai.com/account/api-keys."
)
# Obviously fake. The library echoes the first 8 and the last 4 characters of a key.
FAKE_KEY = "sk-fake-not-a-real-key-0000000000"


def _wrong_key_error() -> openai.AuthenticationError:
    return openai.AuthenticationError(
        _LIBRARY_TEXT, response=httpx.Response(401, request=_REQUEST), body=None
    )


def _failing_openai(monkeypatch, error: Exception) -> None:
    """The module's client, replaced by one whose call raises ``error`` (a wrong key, say)."""

    class FailingTranscriptions:
        def create(self, **kwargs: Any) -> str:
            raise error

    class FailingClient:
        def __init__(self, api_key: str) -> None:
            self.audio = types.SimpleNamespace(transcriptions=FailingTranscriptions())

    monkeypatch.setattr(openai_module, "OpenAI", FailingClient)


def test_openai_engine_hides_the_library_text_and_keeps_only_the_type_and_the_status(monkeypatch):
    _failing_openai(monkeypatch, _wrong_key_error())
    removed: list[str] = []
    real_remove = openai_module._remove_temp_file
    monkeypatch.setattr(
        openai_module, "_remove_temp_file", lambda path: (removed.append(path), real_remove(path))
    )

    with pytest.raises(TranscriptionFailed) as raised:
        asyncio.run(OpenAIWhisperTranscription(FAKE_KEY).transcribe_batch(_pcm_chunk(5), 16000))

    assert str(raised.value) == "OpenAI request failed: AuthenticationError (HTTP 401)"
    assert "sk-" not in str(raised.value) and FAKE_KEY not in str(raised.value)
    assert raised.value.__cause__ is None and raised.value.__suppress_context__ is True
    # the temporary WAV is still removed
    assert len(removed) == 1 and not os.path.exists(removed[0])


def test_openai_engine_names_only_the_type_when_the_error_has_no_status(monkeypatch):
    _failing_openai(monkeypatch, openai.APIConnectionError(request=_REQUEST))

    with pytest.raises(TranscriptionFailed) as raised:
        asyncio.run(OpenAIWhisperTranscription("k").transcribe_batch(_pcm_chunk(5), 16000))

    assert str(raised.value) == "OpenAI request failed: APIConnectionError"


def test_openai_engine_lets_an_error_that_is_not_the_librarys_through_unchanged(monkeypatch):
    _failing_openai(monkeypatch, ValueError("boom"))

    with pytest.raises(ValueError, match="boom") as raised:
        asyncio.run(OpenAIWhisperTranscription("k").transcribe_batch(_pcm_chunk(5), 16000))

    assert type(raised.value) is ValueError


# --- the local engine builds its model from the settings it is given (T-01.2.3) ---


class BuiltModels:
    """Replaces ``WhisperModel`` and remembers how each one was built; no model is downloaded."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, name: str, **kwargs: Any) -> RecordingModel:
        self.calls.append((name, kwargs))
        return RecordingModel()


def _fake_whisper_model(monkeypatch) -> BuiltModels:
    built = BuiltModels()
    monkeypatch.setattr(
        "infrastructure.outbound.local_whisper.local_whisper_transcription.WhisperModel", built
    )
    return built


def test_local_engine_without_settings_builds_the_model_it_always_did(monkeypatch):
    built = _fake_whisper_model(monkeypatch)

    LocalWhisperTranscription()

    assert built.calls == [("small.en", {"device": "cpu", "compute_type": "int8", "cpu_threads": 2})]


def test_local_engine_passes_its_model_threads_and_compute_type_to_the_model(monkeypatch):
    built = _fake_whisper_model(monkeypatch)

    LocalWhisperTranscription(model_name="small", cpu_threads=4, compute_type="float32")
    LocalWhisperTranscription(model_name="tiny.en", cpu_threads=0, compute_type="int8_float16")

    assert built.calls == [
        ("small", {"device": "cpu", "compute_type": "float32", "cpu_threads": 4}),
        ("tiny.en", {"device": "cpu", "compute_type": "int8_float16", "cpu_threads": 0}),
    ]


def test_local_engine_logs_the_compute_type_it_really_uses_not_a_fixed_one(monkeypatch):
    _fake_whisper_model(monkeypatch)

    with capture("stt") as logs:
        LocalWhisperTranscription(model_name="small", cpu_threads=4, compute_type="float32")

    (loading,) = [r for r in logs.records if r["message"] == "Loading local Whisper model on CPU"]
    assert (loading["model_name"], loading["compute_type"], loading["cpu_threads"]) == (
        "small",
        "float32",
        4,
    )
    assert not [r for r in logs.records if "int8" in r["message"]]


def test_the_engine_and_the_config_agree_on_the_defaults():
    from infrastructure.config.stt_config import SttConfig
    from infrastructure.outbound.local_whisper import local_whisper_transcription as local_module

    cfg = SttConfig.from_env({})

    assert (cfg.model, cfg.threads, cfg.compute_type) == (
        local_module.DEFAULT_MODEL_NAME,
        local_module.DEFAULT_CPU_THREADS,
        local_module.DEFAULT_COMPUTE_TYPE,
    )
