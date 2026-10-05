"""STT's stream directions against the project contracts, built and decoded with the codec.

Inbound  : what Brain sends (STT inbound contract) must be accepted and become utterances.
Outbound : what STT sends (STT outbound contract) must decode, as SSE and as NDJSON.
"""

import asyncio
import base64

import httpx
from contracts.stream.codec import EventSequencer, NdjsonDecoder, SseDecoder, encode_ndjson
from contracts.stream.common.base import EventType
from contracts.stream.common.error import ErrorEvent, ErrorEventDTO
from contracts.stream.common.heartbeat import HeartbeatEvent
from contracts.stream.microservices.stt.inbound.completed import (
    STTCompletedInboundEvent,
    STTCompletedInboundEventDTO,
)
from contracts.stream.microservices.stt.inbound.stream_started import (
    STTStreamStartedInboundEvent,
    STTStreamStartedInboundEventDTO,
)
from contracts.stream.microservices.stt.inbound.utterance import (
    STTUtteranceInboundEvent,
    STTUtteranceInboundEventDTO,
)
from contracts.stream.schemas import STT_OUTBOUND

from domain.value_objects.audio_utterance import AudioUtterance
from tests.infrastructure.test_http_handler import FakeService, RecordingSetService, _build_app

NDJSON = {"Content-Type": "application/x-ndjson"}


def _b64(audio: bytes) -> str:
    return base64.b64encode(audio).decode("ascii")


def _brain_upload(*items: tuple, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """An upload as Brain builds it: stream_started first, then the given (class, payload) pairs."""
    sequence = EventSequencer()
    started = sequence.next(
        STTStreamStartedInboundEvent,
        STTStreamStartedInboundEventDTO(sample_rate=sample_rate, channels=channels),
    )
    events = [started, *(sequence.next(cls, payload) for cls, payload in items)]
    return b"".join(encode_ndjson(event) for event in events)


def _post(app, path: str, **kwargs) -> httpx.Response:
    async def run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(kwargs.pop("method", "POST"), path, **kwargs)

    return asyncio.run(run())


def _utterance(audio: bytes, rate: int = 16000) -> tuple:
    return STTUtteranceInboundEvent, STTUtteranceInboundEventDTO(
        bytes_base64=_b64(audio), sample_rate=rate
    )


def test_a_brain_upload_becomes_utterances_and_is_acknowledged_with_contract_events():
    service = RecordingSetService()
    body = _brain_upload(
        _utterance(b"\x01\x02", 16000),
        (HeartbeatEvent, None),
        _utterance(b"\x03\x04", 22050),
        (STTCompletedInboundEvent, STTCompletedInboundEventDTO(output_bytes_base64="")),
    )

    response = _post(_build_app(service), "/process/stream/set", content=body, headers=NDJSON)

    assert service.utterances == [
        AudioUtterance(b"\x01\x02", 16000),
        AudioUtterance(b"\x03\x04", 22050),
    ]  # the heartbeat and a completed event without audio are not utterances
    ack = [*SseDecoder(STT_OUTBOUND).feed(response.content)]
    assert [e.type for e in ack] == [EventType.START_STREAM, EventType.INPUT_COMPLETED]
    assert ack[-1].payload.reason == "end_of_input"


def test_a_completed_event_with_audio_is_one_more_utterance_at_the_announced_rate():
    service = RecordingSetService()
    body = _brain_upload(
        (STTCompletedInboundEvent, STTCompletedInboundEventDTO(output_bytes_base64=_b64(b"whole"[:4]))),
        sample_rate=8000,
    )

    _post(_build_app(service), "/process/stream/set", content=body, headers=NDJSON)

    assert service.utterances == [AudioUtterance(b"whol", 8000)]


def test_the_ack_can_be_asked_for_as_ndjson():
    response = _post(
        _build_app(RecordingSetService()),
        "/process/stream/set",
        content=_brain_upload(_utterance(b"xy")),
        headers={**NDJSON, "Accept": "application/x-ndjson"},
    )

    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert [e.type for e in NdjsonDecoder(STT_OUTBOUND).feed(response.content)] == [
        EventType.START_STREAM,
        EventType.INPUT_COMPLETED,
    ]


def test_contract_violations_in_the_upload_are_reported_as_an_error_event():
    sequence = EventSequencer()
    body = encode_ndjson(sequence.next(*_utterance(b"xy")))  # no stream_started first

    response = _post(_build_app(RecordingSetService()), "/process/stream/set", content=body, headers=NDJSON)

    events = [*SseDecoder(STT_OUTBOUND).feed(response.content)]
    assert events[-1].type is EventType.ERROR and events[-1].payload.code == "stream_failed"


def test_an_upstream_error_event_is_reported_as_an_error_event():
    body = _brain_upload(
        (ErrorEvent, ErrorEventDTO(code="mic_down", message="device lost", recoverable=False))
    )

    response = _post(_build_app(RecordingSetService()), "/process/stream/set", content=body, headers=NDJSON)

    last = [*SseDecoder(STT_OUTBOUND).feed(response.content)][-1]
    assert last.type is EventType.ERROR and "mic_down: device lost" in last.payload.message


def test_an_upload_that_is_not_mono_is_rejected_in_the_ack():
    body = _brain_upload(_utterance(b"xy"), channels=2)

    response = _post(_build_app(RecordingSetService()), "/process/stream/set", content=body, headers=NDJSON)

    last = [*SseDecoder(STT_OUTBOUND).feed(response.content)][-1]
    assert last.type is EventType.ERROR and "2 channels" in last.payload.message


def test_half_a_sample_of_audio_is_rejected_in_the_ack():
    body = _brain_upload(_utterance(b"xyz"))

    response = _post(_build_app(RecordingSetService()), "/process/stream/set", content=body, headers=NDJSON)

    last = [*SseDecoder(STT_OUTBOUND).feed(response.content)][-1]
    assert last.type is EventType.ERROR and "whole number of samples" in last.payload.message


def test_audio_that_is_not_base64_is_rejected_in_the_ack():
    sequence = EventSequencer()
    body = b"".join(
        encode_ndjson(event)
        for event in (
            sequence.next(
                STTStreamStartedInboundEvent, STTStreamStartedInboundEventDTO(sample_rate=16000, channels=1)
            ),
            sequence.next(
                STTUtteranceInboundEvent,
                STTUtteranceInboundEventDTO(bytes_base64="not base64!!", sample_rate=16000),
            ),
        )
    )

    response = _post(_build_app(RecordingSetService()), "/process/stream/set", content=body, headers=NDJSON)

    last = [*SseDecoder(STT_OUTBOUND).feed(response.content)][-1]
    assert last.type is EventType.ERROR and "not valid base64" in last.payload.message


def test_transcripts_decode_with_the_stt_outbound_contract_in_both_framings():
    for headers, decoder_cls in (({}, SseDecoder), ({"Accept": "application/x-ndjson"}, NdjsonDecoder)):
        app = _build_app(FakeService(get_items=["hello there", "second one"]))

        response = _post(app, "/process/stream/get", method="GET", headers=headers)

        events = [*decoder_cls(STT_OUTBOUND).feed(response.content)]
        assert [e.type for e in events] == [
            EventType.START_STREAM,
            EventType.PARTIAL,
            EventType.COMPLETED,
            EventType.PARTIAL,
            EventType.COMPLETED,
        ]
        assert [e.payload.output for e in events if e.type is EventType.COMPLETED] == [
            "hello there",
            "second one",
        ]
