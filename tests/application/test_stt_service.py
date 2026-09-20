import asyncio
from collections.abc import AsyncIterator

import pytest

from application.dtos.completed_audio_segment import CompletedAudioSegment
from application.dtos.process_batch_inbound import ProcessBatchInboundDTO
from application.dtos.process_stream_inbound import ProcessStreamInboundDTO
from application.dtos.set_stream_inbound import SetStreamInboundDTO
from application.errors import NoActiveStream, SharedStreamForwardingError
from application.ports.outbound.transcription_port import TranscriptionPort
from application.services.stt_service import SttService
from domain.errors import InvalidStreamSettings
from domain.value_objects.stream_settings import StreamSettings


class FakeTranscription(TranscriptionPort):
    """Streams one text per non-empty audio chunk; batches echo their byte count."""

    def __init__(self, fail_with: Exception | None = None, available: bool = True) -> None:
        self.settings: list[StreamSettings] = []
        self.batches: list[tuple[bytes, int]] = []
        self.fail_with = fail_with
        self.available = available

    async def transcribe_stream(
        self, settings: StreamSettings, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[str]:
        self.settings.append(settings)

        async def texts() -> AsyncIterator[str]:
            async for chunk in audio_stream:
                if self.fail_with is not None:
                    raise self.fail_with
                if chunk:
                    yield f"heard {len(chunk)}"

        return texts()

    async def transcribe_batch(self, audio_data: bytes, sample_rate: int) -> str:
        self.batches.append((audio_data, sample_rate))
        return f"  batch {len(audio_data)}  "

    def is_available(self) -> bool:
        return self.available


async def _audio(*items):
    for item in items:
        yield item


async def _collect(stream: AsyncIterator[str]) -> list[str]:
    return [text async for text in stream]


def test_process_stream_hands_validated_settings_and_audio_to_the_engine():
    async def run() -> None:
        engine = FakeTranscription()
        service = SttService(engine)

        result = await service.process_stream(
            ProcessStreamInboundDTO(
                audio_stream=_audio(b"ab", b"", b"cde"), sample_rate=8000, chunk_size=512
            )
        )

        assert await _collect(result.text_stream) == ["heard 2", "heard 3"]
        assert engine.settings == [StreamSettings(sample_rate=8000, chunk_size=512)]

    asyncio.run(run())


def test_invalid_settings_are_rejected_before_reaching_the_engine():
    async def run() -> None:
        engine = FakeTranscription()
        service = SttService(engine)

        with pytest.raises(InvalidStreamSettings):
            await service.process_stream(
                ProcessStreamInboundDTO(audio_stream=_audio(), chunk_size=0)
            )
        with pytest.raises(InvalidStreamSettings):
            await service.set_stream(SetStreamInboundDTO(audio_stream=_audio(), sample_rate=0))
        assert engine.settings == []

    asyncio.run(run())


def test_process_batch_returns_the_engine_text():
    async def run() -> None:
        engine = FakeTranscription()
        result = await SttService(engine).process_batch(
            ProcessBatchInboundDTO(audio_data=b"abcd", sample_rate=8000)
        )
        assert result.text == "  batch 4  "
        assert engine.batches == [(b"abcd", 8000)]

    asyncio.run(run())


def test_availability_comes_from_the_engine():
    assert SttService(FakeTranscription(available=True)).is_available() is True
    assert SttService(FakeTranscription(available=False)).is_available() is False


def test_get_stream_before_any_set_stream_raises_no_active_stream():
    async def run() -> None:
        with pytest.raises(NoActiveStream):
            await SttService(FakeTranscription()).get_stream()

    asyncio.run(run())


def test_no_active_stream_is_still_a_runtime_error():
    assert issubclass(NoActiveStream, RuntimeError)


def test_set_stream_forwards_engine_text_to_get_stream():
    async def run() -> None:
        service = SttService(FakeTranscription())

        await service.set_stream(SetStreamInboundDTO(audio_stream=_audio(b"ab", b"cde")))
        result = await service.get_stream()

        assert await _collect(result.text_stream) == ["heard 2", "heard 3"]

    asyncio.run(run())


def test_completed_segments_are_transcribed_as_batches_and_stripped():
    async def run() -> None:
        engine = FakeTranscription()
        service = SttService(engine)
        segment = CompletedAudioSegment(audio_data=b"wxyz", source_sequence=7)

        await service.set_stream(
            SetStreamInboundDTO(audio_stream=_audio(b"ab", segment), sample_rate=8000)
        )
        result = await service.get_stream()

        assert await _collect(result.text_stream) == ["heard 2", "batch 4"]
        assert engine.batches == [(b"wxyz", 8000)]

    asyncio.run(run())


def test_an_engine_failure_reaches_the_reader_of_the_shared_stream():
    async def run() -> None:
        service = SttService(FakeTranscription(fail_with=RuntimeError("backend down")))

        await service.set_stream(SetStreamInboundDTO(audio_stream=_audio(b"ab")))
        result = await service.get_stream()

        with pytest.raises(SharedStreamForwardingError, match="backend down"):
            await _collect(result.text_stream)

    asyncio.run(run())


def test_stop_stream_cancels_a_running_set_stream():
    async def run() -> None:
        service = SttService(FakeTranscription())
        gate = asyncio.Event()

        async def endless():
            yield b"ab"
            await gate.wait()

        set_task = asyncio.create_task(
            service.set_stream(SetStreamInboundDTO(audio_stream=endless()))
        )
        await asyncio.sleep(0.05)

        await service.stop_stream()

        with pytest.raises(asyncio.CancelledError):
            await set_task

    asyncio.run(run())


def test_stop_stream_after_completion_ends_the_text_stream():
    async def run() -> None:
        service = SttService(FakeTranscription())
        await service.set_stream(SetStreamInboundDTO(audio_stream=_audio(b"ab")))

        await service.stop_stream()
        result = await service.get_stream()

        assert await _collect(result.text_stream) == ["heard 2"]

    asyncio.run(run())


def test_stop_stream_without_any_stream_is_harmless():
    asyncio.run(SttService(FakeTranscription()).stop_stream())
