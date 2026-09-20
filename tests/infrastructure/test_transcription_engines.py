"""The two engines against fake models / clients; no network and no model download."""

import asyncio
import os
import types
from typing import Any

import numpy as np

from domain.value_objects.stream_settings import StreamSettings
from infrastructure.outbound.local_whisper.local_whisper_transcription import (
    LocalWhisperTranscription,
    _LocalTextStream,
    _pcm_to_whisper_input,
)
from infrastructure.outbound.openai_whisper import openai_whisper_transcription as openai_module
from infrastructure.outbound.openai_whisper.openai_whisper_transcription import (
    OpenAIWhisperTranscription,
    _OpenAITextStream,
)

SETTINGS = StreamSettings(sample_rate=16000, chunk_size=1024, silence_threshold=150)


async def _audio_stream(chunks: list[bytes]):
    for chunk in chunks:
        yield chunk


def _pcm_chunk(value: int, samples: int = 1024) -> bytes:
    return np.full(samples, value, dtype=np.int16).tobytes()


class FakeLocalModel:
    def __init__(self) -> None:
        self.language: str | None = None
        self.calls = 0

    def transcribe(self, audio_data: Any, **kwargs: Any):
        self.language = kwargs["language"]
        self.calls += 1

        class Segment:
            text = " final local text"

        return [Segment()], None


def test_local_stream_flushes_final_buffer_when_audio_input_ends():
    async def run() -> str:
        model = FakeLocalModel()
        stream = _LocalTextStream(SETTINGS, _audio_stream([_pcm_chunk(10000)]), model, "es")
        text = await stream.__anext__()
        assert model.language == "es"
        return text

    assert asyncio.run(run()) == "final local text"


def test_local_stream_ends_after_the_last_utterance():
    async def run() -> list[str]:
        stream = _LocalTextStream(
            SETTINGS, _audio_stream([_pcm_chunk(10000)]), FakeLocalModel(), "en"
        )
        return [text async for text in stream]

    assert asyncio.run(run()) == ["final local text"]


def test_local_stream_splits_utterances_on_silence():
    async def run() -> list[str]:
        settings = StreamSettings(16000, 1024, 150, 0.1)  # 1 silent chunk ends an utterance
        loud, quiet = _pcm_chunk(10000), _pcm_chunk(0)
        chunks = [loud] * 3 + [quiet] * 60 + [loud] * 3 + [quiet] * 60
        model = FakeLocalModel()
        stream = _LocalTextStream(settings, _audio_stream(chunks), model, "en")
        texts = [text async for text in stream]
        assert model.calls == 2
        return texts

    assert asyncio.run(run()) == ["final local text", "final local text"]


def test_pcm_is_resampled_to_16k_for_whisper():
    samples = _pcm_to_whisper_input(np.zeros(8000, dtype=np.int16).tobytes(), 8000)
    assert samples.dtype == np.float32 and len(samples) == 16000


def test_local_batch_transcription_and_availability(monkeypatch):
    fake = types.ModuleType("faster_whisper")
    fake.WhisperModel = lambda *args, **kwargs: FakeLocalModel()  # type: ignore[attr-defined]
    monkeypatch.setattr(
        "infrastructure.outbound.local_whisper.local_whisper_transcription.WhisperModel",
        fake.WhisperModel,
    )
    engine = LocalWhisperTranscription(language="es")

    text = asyncio.run(engine.transcribe_batch(_pcm_chunk(1000), 16000))

    assert text == " final local text"
    assert engine.is_available() is True


def test_openai_stream_flushes_final_buffer_when_audio_input_ends():
    async def run() -> str:
        stream = _OpenAITextStream(SETTINGS, _audio_stream([]), client=object(), language="en")  # type: ignore[arg-type]
        stream._is_speaking = True
        stream._audio_buffer.extend(_pcm_chunk(1000))

        async def fake_transcribe() -> str:
            stream._reset_buffers()
            return "final openai text"

        stream._transcribe_utterance = fake_transcribe  # type: ignore[method-assign]
        return await stream.__anext__()

    assert asyncio.run(run()) == "final openai text"


def test_openai_stream_transcribes_speech_and_stops_when_audio_ends():
    async def run() -> list[str]:
        # The quietest chunk seen becomes the noise floor, so start with some background noise.
        noise_then_speech = [_pcm_chunk(50)] * 5 + [_pcm_chunk(10000)] * 3
        stream = _OpenAITextStream(
            SETTINGS,
            _audio_stream(noise_then_speech),
            client=object(),
            language="en",  # type: ignore[arg-type]
        )
        sent: list[int] = []

        def fake_transcribe(raw_pcm: bytes, sample_rate: int) -> str:
            sent.append(len(raw_pcm))
            return "hello"

        stream._transcribe_with_openai = fake_transcribe  # type: ignore[method-assign]
        texts = [text async for text in stream]
        assert sent  # the speech that was heard was sent, in whole samples
        assert all(n % 2 == 0 for n in sent)
        return texts

    assert asyncio.run(run()) == ["hello"]


def test_openai_stream_ignores_silence():
    async def run() -> list[str]:
        stream = _OpenAITextStream(
            SETTINGS,
            _audio_stream([_pcm_chunk(0)] * 5),
            client=object(),
            language="en",  # type: ignore[arg-type]
        )
        return [text async for text in stream]

    assert asyncio.run(run()) == []


def test_openai_engine_availability_follows_the_api_key():
    assert OpenAIWhisperTranscription(api_key="k").is_available() is True
    assert OpenAIWhisperTranscription(api_key="").is_available() is False


def test_openai_batch_calls_the_api_with_a_wav_and_cleans_up(monkeypatch):
    calls: list[dict[str, Any]] = []

    class FakeTranscriptions:
        def create(self, **kwargs: Any) -> str:
            calls.append({**kwargs, "riff": kwargs["file"].read(4)})
            return "  hola  "

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            self.audio = types.SimpleNamespace(transcriptions=FakeTranscriptions())

    removed: list[str] = []
    real_remove = openai_module._remove_temp_file
    monkeypatch.setattr(openai_module, "OpenAI", FakeClient)
    monkeypatch.setattr(
        openai_module, "_remove_temp_file", lambda path: (removed.append(path), real_remove(path))
    )

    text = asyncio.run(OpenAIWhisperTranscription("k", "es").transcribe_batch(_pcm_chunk(5), 16000))

    assert text == "hola"
    assert calls[0]["language"] == "es" and calls[0]["model"] == "whisper-1"
    assert calls[0]["riff"] == b"RIFF"
    assert len(removed) == 1
    assert not os.path.exists(removed[0])
