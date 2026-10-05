"""The two engines against fake models / clients; no network and no model download."""

import asyncio
import os
import types
from typing import Any

import numpy as np

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
