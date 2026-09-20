"""STT's stream directions against the project contracts, built and decoded with the codec.

Inbound  : what Brain sends (STT inbound contract) must be accepted and become audio.
Outbound : what STT sends (STT outbound contract) must decode, as SSE and as NDJSON.
"""

import asyncio
import base64

import httpx
from contracts.stream.codec import EventSequencer, NdjsonDecoder, SseDecoder, encode_ndjson
from contracts.stream.common.base import EventType
from contracts.stream.common.error import ErrorEvent, ErrorEventDTO
from contracts.stream.common.heartbeat import HeartbeatEvent
from contracts.stream.microservices.stt.inbound.stream_started import (
    STTStreamStartedInboundEvent,
    STTStreamStartedInboundEventDTO,
)
from contracts.stream.microservices.stt.inbound.completed import (
    STTCompletedInboundEvent,
    STTCompletedInboundEventDTO,
)
from contracts.stream.microservices.stt.inbound.partial import (
    STTPartialInboundEvent,
    STTPartialInboundEventDTO,
)
from contracts.stream.schemas import STT_OUTBOUND

from application.dtos.completed_audio_segment import CompletedAudioSegment
from domain.value_objects.stream_settings import StreamSettings
from tests.infrastructure.test_http_handler import FakeService, RecordingSetService, _build_app

NDJSON = {"Content-Type": "application/x-ndjson"}


def _b64(audio: bytes) -> str:
    return base64.b64encode(audio).decode("ascii")


def _brain_upload(*items: tuple) -> bytes:
    """An upload as Brain builds it: stream_started first, then the given (class, payload) pairs."""
    sequence = EventSequencer()
    started = sequence.next(
        STTStreamStartedInboundEvent, STTStreamStartedInboundEventDTO(sample_rate=16000, channels=1)
    )
    events = [started, *(sequence.next(cls, payload) for cls, payload in items)]
    return b"".join(encode_ndjson(event) for event in events)


def _post(app, path: str, **kwargs) -> httpx.Response:
    async def run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(kwargs.pop("method", "POST"), path, **kwargs)

    return asyncio.run(run())


def _partial(audio: bytes) -> tuple:
    return STTPartialInboundEvent, STTPartialInboundEventDTO(bytes_base64=_b64(audio))


def test_a_brain_upload_becomes_audio_and_is_acknowledged_with_contract_events():
    service = RecordingSetService()
    body = _brain_upload(
        _partial(b"\x01\x02"),
        (HeartbeatEvent, None),
        _partial(b"\x03\x04"),
        (STTCompletedInboundEvent, STTCompletedInboundEventDTO(output_bytes_base64="")),
    )

    response = _post(_build_app(service), "/process/stream/set", content=body, headers=NDJSON)

    assert service.audio_chunks[:2] == [b"\x01\x02", b"\x03\x04"]
    assert service.audio_chunks[2:], "a completed event without audio closes the utterance with silence"
    ack = [*SseDecoder(STT_OUTBOUND).feed(response.content)]
    assert [e.type for e in ack] == [EventType.START_STREAM, EventType.INPUT_COMPLETED]
    assert ack[-1].payload.reason == "end_of_input"


def test_a_completed_event_with_audio_is_one_whole_utterance():
    service = RecordingSetService()
    body = _brain_upload(
        (STTCompletedInboundEvent, STTCompletedInboundEventDTO(output_bytes_base64=_b64(b"whole")))
    )

    _post(_build_app(service), "/process/stream/set", content=body, headers=NDJSON)

    (segment,) = service.audio_chunks
    assert isinstance(segment, CompletedAudioSegment) and segment.audio_data == b"whole"


def test_the_ack_can_be_asked_for_as_ndjson():
    response = _post(
        _build_app(RecordingSetService()),
        "/process/stream/set",
        content=_brain_upload(_partial(b"x")),
        headers={**NDJSON, "Accept": "application/x-ndjson"},
    )

    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert [e.type for e in NdjsonDecoder(STT_OUTBOUND).feed(response.content)] == [
        EventType.START_STREAM,
        EventType.INPUT_COMPLETED,
    ]


def test_contract_violations_in_the_upload_are_reported_as_an_error_event():
    sequence = EventSequencer()
    # no stream_started first
    body = encode_ndjson(sequence.next(*_partial(b"x")))

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


def test_an_upload_announcing_another_audio_format_is_rejected_in_the_ack():
    sequence = EventSequencer()
    body = b"".join(
        encode_ndjson(e)
        for e in (
            sequence.next(
                STTStreamStartedInboundEvent, STTStreamStartedInboundEventDTO(sample_rate=44100, channels=1)
            ),
            sequence.next(*_partial(b"x")),
        )
    )

    response = _post(_build_app(RecordingSetService()), "/process/stream/set", content=body, headers=NDJSON)

    last = [*SseDecoder(STT_OUTBOUND).feed(response.content)][-1]
    assert last.type is EventType.ERROR and "44100" in last.payload.message and "16000" in last.payload.message


def test_get_with_settings_that_differ_from_the_active_stream_is_a_422():
    class WithSettings(FakeService):
        def current_settings(self):
            return StreamSettings(sample_rate=16000)

    service = WithSettings(get_items=["x"])
    app = _build_app(service)

    mismatch = _post(app, "/process/stream/get", method="GET", params={"sample_rate": 8000})
    same = _post(app, "/process/stream/get", method="GET", params={"sample_rate": 16000, "chunk_size": 1024})

    assert mismatch.status_code == 422 and "sample_rate=8000" in mismatch.json()["message"]
    assert same.status_code == 200
