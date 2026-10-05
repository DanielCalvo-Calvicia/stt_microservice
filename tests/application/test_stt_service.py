import asyncio
from collections.abc import AsyncIterator

import pytest

from application.dtos.process_batch_inbound import ProcessBatchInboundDTO
from application.dtos.process_stream_inbound import ProcessStreamInboundDTO
from application.dtos.set_stream_inbound import SetStreamInboundDTO
from application.errors import NoActiveStream, SharedStreamForwardingError
from application.ports.outbound.transcription_port import TranscriptionPort
from application.services.stt_service import SttService
from domain.value_objects.audio_utterance import AudioUtterance
from domain.value_objects.utterance import Utterance


class FakeTranscription(TranscriptionPort):
    """Hears ``heard <bytes>`` in every utterance (with blanks around, like a real engine)."""

    def __init__(self, fail_with: Exception | None = None, available: bool = True) -> None:
        self.batches: list[tuple[bytes, int]] = []
        self.fail_with = fail_with
        self.available = available

    async def transcribe_batch(self, audio_data: bytes, sample_rate: int) -> str:
        if self.fail_with is not None:
            raise self.fail_with
        self.batches.append((audio_data, sample_rate))
        return f"  heard {len(audio_data)}  " if audio_data.strip(b"\x00") else "   "

    def is_available(self) -> bool:
        return self.available


async def _utterances(*items: AudioUtterance) -> AsyncIterator[AudioUtterance]:
    for item in items:
        yield item


def _speech(size: int, rate: int = 16000) -> AudioUtterance:
    return AudioUtterance(b"\x01\x00" * (size // 2), rate)


SILENCE = AudioUtterance(b"\x00\x00" * 4, 16000)


async def _collect(stream) -> list:
    return [item async for item in stream]


def test_process_stream_transcribes_each_utterance_at_its_own_rate_and_skips_the_empty_ones():
    async def run() -> None:
        engine = FakeTranscription()
        service = SttService(engine)

        result = await service.process_stream(
            ProcessStreamInboundDTO(utterances=_utterances(_speech(4, 8000), SILENCE, _speech(6)))
        )

        assert await _collect(result.text_stream) == ["heard 4", "heard 6"]
        assert [rate for _, rate in engine.batches] == [8000, 16000, 16000]

    asyncio.run(run())


def test_process_batch_returns_the_engine_text():
    async def run() -> None:
        engine = FakeTranscription()
        result = await SttService(engine).process_batch(
            ProcessBatchInboundDTO(audio_data=b"abcd", sample_rate=8000)
        )
        assert result.text == "  heard 4  "
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


def test_set_stream_forwards_each_utterances_text_to_get_stream():
    async def run() -> None:
        service = SttService(FakeTranscription())

        await service.set_stream(SetStreamInboundDTO(utterances=_utterances(_speech(2), _speech(4))))
        result = await service.get_stream()

        assert await _collect(result.text_stream) == ["heard 2", "heard 4"]

    asyncio.run(run())


def test_the_gate_stream_yields_utterances_with_the_audio_they_came_from():
    async def run() -> None:
        service = SttService(FakeTranscription(), "gate", with_audio=True)

        await service.set_stream(
            SetStreamInboundDTO(utterances=_utterances(_speech(2), SILENCE, _speech(4)))
        )
        result = await service.get_stream()

        assert await _collect(result.text_stream) == [
            Utterance("heard 2", b"\x01\x00"),
            Utterance("heard 4", b"\x01\x00\x01\x00"),
        ]

    asyncio.run(run())


def test_a_plain_service_yields_text_only():
    async def run() -> None:
        service = SttService(FakeTranscription())
        await service.set_stream(SetStreamInboundDTO(utterances=_utterances(_speech(2))))

        assert await _collect((await service.get_stream()).text_stream) == ["heard 2"]

    asyncio.run(run())


def test_an_engine_failure_reaches_the_reader_of_the_shared_stream():
    async def run() -> None:
        service = SttService(FakeTranscription(fail_with=RuntimeError("backend down")))

        await service.set_stream(SetStreamInboundDTO(utterances=_utterances(_speech(2))))
        result = await service.get_stream()

        with pytest.raises(SharedStreamForwardingError, match="backend down"):
            await _collect(result.text_stream)

    asyncio.run(run())


def test_stop_stream_cancels_a_running_set_stream():
    async def run() -> None:
        service = SttService(FakeTranscription())
        gate = asyncio.Event()

        async def endless():
            yield _speech(2)
            await gate.wait()

        set_task = asyncio.create_task(service.set_stream(SetStreamInboundDTO(utterances=endless())))
        await asyncio.sleep(0.05)

        await service.stop_stream()

        with pytest.raises(asyncio.CancelledError):
            await set_task

    asyncio.run(run())


def test_stop_stream_after_completion_ends_the_text_stream():
    async def run() -> None:
        service = SttService(FakeTranscription())
        await service.set_stream(SetStreamInboundDTO(utterances=_utterances(_speech(2))))

        await service.stop_stream()
        result = await service.get_stream()

        assert await _collect(result.text_stream) == ["heard 2"]

    asyncio.run(run())


def test_stop_stream_without_any_stream_is_harmless():
    asyncio.run(SttService(FakeTranscription()).stop_stream())
