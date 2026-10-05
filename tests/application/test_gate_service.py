"""The wake-phrase gate's service: an SttService whose shared stream carries the audio of each utterance."""

import asyncio
from collections.abc import AsyncIterator

import pytest

from application.dtos.process_stream_inbound import ProcessStreamInboundDTO  # noqa: F401 - the port's other use case
from application.dtos.set_stream_inbound import SetStreamInboundDTO
from application.ports.outbound.transcription_port import TranscriptionPort, UtteranceTranscriptionPort
from application.services.stt_service import SttService
from domain.value_objects.stream_settings import StreamSettings
from domain.value_objects.utterance import Utterance


class PlainEngine(TranscriptionPort):
    async def transcribe_stream(self, settings: StreamSettings, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[str]:
        async def texts() -> AsyncIterator[str]:
            async for chunk in audio_stream:
                yield f"text {len(chunk)}"

        return texts()

    async def transcribe_batch(self, audio_data: bytes, sample_rate: int) -> str:
        return "batch"

    def is_available(self) -> bool:
        return True


class GateEngine(PlainEngine, UtteranceTranscriptionPort):
    """Hears each chunk as one utterance and hands back its audio with the text."""

    async def transcribe_utterances(self, settings: StreamSettings, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[Utterance]:
        async def utterances() -> AsyncIterator[Utterance]:
            async for chunk in audio_stream:
                yield Utterance(text=f"oblivion {len(chunk)}", audio=chunk)
                yield Utterance(text="", audio=b"silence")  # an empty transcription is never queued

        return utterances()


async def _audio(*chunks: bytes) -> AsyncIterator[bytes]:
    for chunk in chunks:
        yield chunk


async def _collect(service: SttService) -> list:
    stream = await service.get_stream()
    return [item async for item in stream.text_stream]


def test_the_gate_stream_yields_utterances_with_their_audio() -> None:
    async def run() -> list:
        service = SttService(GateEngine(), "gate", with_audio=True)
        await service.set_stream(SetStreamInboundDTO(audio_stream=_audio(b"abc", b"defgh"), sample_rate=16000, chunk_size=1024, silence_threshold=150, silence_limit_seconds=2.0))
        return await _collect(service)

    items = asyncio.run(run())

    assert items == [Utterance("oblivion 3", b"abc"), Utterance("oblivion 5", b"defgh")]


def test_a_plain_service_still_yields_text_only() -> None:
    async def run() -> list:
        service = SttService(GateEngine(), "stt")  # an engine that CAN return audio, asked not to
        await service.set_stream(SetStreamInboundDTO(audio_stream=_audio(b"abc"), sample_rate=16000, chunk_size=1024, silence_threshold=150, silence_limit_seconds=2.0))
        return await _collect(service)

    assert asyncio.run(run()) == ["text 3"]


def test_an_engine_that_cannot_return_audio_cannot_be_the_gate() -> None:
    with pytest.raises(TypeError, match="cannot return the audio"):
        SttService(PlainEngine(), "gate", with_audio=True)
