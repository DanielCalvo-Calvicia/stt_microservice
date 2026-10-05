import asyncio
import base64
import json
from collections.abc import AsyncIterator

import httpx
from contracts.stream.codec import EventSequencer, encode_ndjson
from contracts.stream.microservices.stt.inbound.stream_started import (
    STTStreamStartedInboundEvent,
    STTStreamStartedInboundEventDTO,
)
from contracts.stream.microservices.stt.inbound.utterance import (
    STTUtteranceInboundEvent,
    STTUtteranceInboundEventDTO,
)
from fastapi import FastAPI

from application.dtos.batch_transcription_outbound import BatchTranscriptionOutboundDTO
from application.dtos.process_batch_inbound import ProcessBatchInboundDTO
from application.dtos.process_stream_inbound import ProcessStreamInboundDTO
from application.dtos.set_stream_inbound import SetStreamInboundDTO
from application.dtos.text_stream_outbound import TextStreamOutboundDTO
from application.ports.inbound.stt_transcription_port import SttTranscriptionPort
from application.ports.outbound.transcription_port import TranscriptionPort
from application.services.stt_service import SttService
from domain.value_objects.audio_utterance import AudioUtterance
from infrastructure.inbound.http.http_handler import SttHandler

NDJSON = {"Content-Type": "application/x-ndjson"}


def upload_body(*utterances: bytes, sample_rate: int = 16000) -> bytes:
    """An upload as Brain builds it: ``stream_started``, then one ``utterance`` event per utterance."""
    sequence = EventSequencer()
    events = [
        sequence.next(
            STTStreamStartedInboundEvent,
            STTStreamStartedInboundEventDTO(sample_rate=sample_rate, channels=1),
        )
    ]
    for audio in utterances:
        events.append(
            sequence.next(
                STTUtteranceInboundEvent,
                STTUtteranceInboundEventDTO(
                    bytes_base64=base64.b64encode(audio).decode("ascii"), sample_rate=sample_rate
                ),
            )
        )
    return b"".join(encode_ndjson(event) for event in events)


def _parse_sse_events(body: str) -> list[dict]:
    events = []
    for line in body.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line.removeprefix("data: ")))
        elif line.strip():
            raise AssertionError(f"Unexpected raw stream line: {line!r}")
    return events


def _parse_ndjson_events(body: str) -> list[dict]:
    return [json.loads(line) for line in body.splitlines() if line.strip()]


def _assert_event_shape(event: dict, expected_type: str, expected_sequence: int) -> None:
    assert set(event) == {"type", "sequence", "timestamp", "payload"}
    assert event["type"] == expected_type
    assert event["sequence"] == expected_sequence
    assert event["timestamp"].endswith("Z")
    assert isinstance(event["payload"], dict)


async def _text_stream(items: list[str]) -> AsyncIterator[str]:
    for item in items:
        yield item


async def _failing_text_stream() -> AsyncIterator[str]:
    raise RuntimeError("transcription backend unavailable")
    yield ""


async def _text_then_failing_stream() -> AsyncIterator[str]:
    yield "hello before failure"
    raise RuntimeError("transcription backend unavailable")


class FakeService(SttTranscriptionPort):
    def __init__(
        self,
        *,
        process_items: list[str] | None = None,
        get_items: list[str] | None = None,
        fail_process_stream: bool = False,
        fail_process_stream_after_text: bool = False,
    ) -> None:
        self.process_items = process_items or []
        self.get_items = get_items or []
        self.fail_process_stream = fail_process_stream
        self.fail_process_stream_after_text = fail_process_stream_after_text

    async def process_stream(self, request: ProcessStreamInboundDTO) -> TextStreamOutboundDTO:
        if self.fail_process_stream:
            return TextStreamOutboundDTO(text_stream=_failing_text_stream())
        if self.fail_process_stream_after_text:
            return TextStreamOutboundDTO(text_stream=_text_then_failing_stream())
        return TextStreamOutboundDTO(text_stream=_text_stream(self.process_items))

    async def set_stream(self, request: SetStreamInboundDTO) -> None:
        return None

    async def get_stream(self) -> TextStreamOutboundDTO:
        return TextStreamOutboundDTO(text_stream=_text_stream(self.get_items))

    async def stop_stream(self) -> None:
        return None

    async def process_batch(self, request: ProcessBatchInboundDTO) -> BatchTranscriptionOutboundDTO:
        return BatchTranscriptionOutboundDTO(text="")

    def is_available(self) -> bool:
        return True


class RecordingSetService(FakeService):
    def __init__(self) -> None:
        super().__init__()
        self.utterances: list[AudioUtterance] = []

    async def set_stream(self, request: SetStreamInboundDTO) -> None:
        async for utterance in request.utterances:
            self.utterances.append(utterance)


class FakeTranscription(TranscriptionPort):
    """Answers the given texts, one per utterance, in order (an empty text = no speech in it)."""

    def __init__(self, texts: list[str] | None = None) -> None:
        self.texts = ["adapter text"] if texts is None else texts
        self.calls = 0

    async def transcribe_batch(self, audio_data: bytes, sample_rate: int) -> str:
        text = self.texts[self.calls % len(self.texts)] if self.texts else ""
        self.calls += 1
        return text

    def is_available(self) -> bool:
        return True


def _app_for(service: SttTranscriptionPort) -> FastAPI:
    app = FastAPI()
    app.include_router(SttHandler(service).router)
    return app


def _build_app(service: FakeService) -> FastAPI:
    return _app_for(service)


async def _request_events(app: FastAPI, method: str, path: str) -> list[dict]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        if method == "POST":
            response = await client.post(path, content=upload_body(b"\x01\x00"), headers=NDJSON)
        else:
            response = await client.get(path)
    assert response.status_code == 200
    return _parse_sse_events(response.text)


async def _request_decoupled_events(app: FastAPI, *utterances: bytes) -> list[dict]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        body = upload_body(*(utterances or (b"\x01\x00",)))
        set_response = await client.post("/process/stream/set", content=body, headers=NDJSON)
        assert set_response.status_code == 200

        get_response = await client.get("/process/stream/get")
        assert get_response.status_code == 200

    return _parse_sse_events(get_response.text)


def test_process_stream_starts_with_stream_started() -> None:
    app = _build_app(FakeService(process_items=["hello world"]))

    events = asyncio.run(_request_events(app, "POST", "/process/stream"))

    _assert_event_shape(events[0], "stream_started", 1)
    assert events[0]["payload"] == {}


def test_process_stream_emits_no_chunks_when_no_text_is_parsed() -> None:
    app = _build_app(FakeService(process_items=[]))

    events = asyncio.run(_request_events(app, "POST", "/process/stream"))

    _assert_event_shape(events[0], "stream_started", 1)
    _assert_event_shape(events[1], "completed", 2)
    assert events[1]["payload"] == {"reason": "completed", "output": "", "audio_base64": ""}


def test_process_stream_ignores_empty_adapter_text_chunks() -> None:
    app = _build_app(FakeService(process_items=["", "hello world", ""]))

    events = asyncio.run(_request_events(app, "POST", "/process/stream"))

    assert [event["type"] for event in events] == ["stream_started", "partial", "completed"]
    assert events[1]["payload"] == {"text": "hello world"}


def test_process_stream_emits_partial_and_completed_events() -> None:
    app = _build_app(FakeService(process_items=["hello world"]))

    events = asyncio.run(_request_events(app, "POST", "/process/stream"))

    _assert_event_shape(events[1], "partial", 2)
    assert events[1]["payload"] == {"text": "hello world"}
    _assert_event_shape(events[2], "completed", 3)
    assert events[2]["payload"] == {"reason": "completed", "output": "hello world", "audio_base64": ""}


def test_stream_can_continue_after_completed_event() -> None:
    app = _build_app(FakeService(process_items=["first utterance", "second utterance"]))

    events = asyncio.run(_request_events(app, "POST", "/process/stream"))

    assert [event["type"] for event in events] == [
        "stream_started",
        "partial",
        "completed",
        "partial",
        "completed",
    ]
    assert events[2]["payload"]["output"] == "first utterance"
    assert events[3]["payload"]["text"] == "second utterance"


def test_get_stream_uses_same_event_contract() -> None:
    app = _build_app(FakeService(get_items=["queued utterance"]))

    events = asyncio.run(_request_events(app, "GET", "/process/stream/get"))

    _assert_event_shape(events[0], "stream_started", 1)
    _assert_event_shape(events[1], "partial", 2)
    _assert_event_shape(events[2], "completed", 3)
    assert events[2]["payload"]["output"] == "queued utterance"


def test_set_stream_returns_standard_stream_events() -> None:
    app = _build_app(FakeService())
    transport = httpx.ASGITransport(app=app)

    async def run():
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(
                "/process/stream/set", content=upload_body(b"\x01\x00"), headers=NDJSON
            )

    response = asyncio.run(run())

    assert response.status_code == 200
    assert response.headers["x-action"] == "set_stream"
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse_events(response.text)
    assert [event["type"] for event in events] == ["stream_started", "input_completed"]
    assert events[1]["payload"] == {"reason": "end_of_input"}


def test_set_stream_hands_the_application_the_utterances_of_the_events() -> None:
    service = RecordingSetService()
    app = _build_app(service)

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            await client.post(
                "/process/stream/set",
                content=upload_body(b"\x01\x00\x02\x00", b"\x03\x00", sample_rate=22050),
                headers=NDJSON,
            )

    asyncio.run(run())

    assert service.utterances == [
        AudioUtterance(b"\x01\x00\x02\x00", 22050),
        AudioUtterance(b"\x03\x00", 22050),
    ]


def test_get_stream_can_return_ndjson_events() -> None:
    app = _build_app(FakeService(get_items=["queued utterance"]))
    transport = httpx.ASGITransport(app=app)

    async def run():
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(
                "/process/stream/get", headers={"Accept": "application/x-ndjson"}
            )

    response = asyncio.run(run())

    assert response.headers["content-type"].startswith("application/x-ndjson")
    events = _parse_ndjson_events(response.text)
    _assert_event_shape(events[0], "stream_started", 1)
    _assert_event_shape(events[2], "completed", 3)
    assert events[1]["payload"] == {"text": "queued utterance"}


def test_decoupled_stream_returns_text_from_the_engine_to_get_stream() -> None:
    app = _app_for(SttService(FakeTranscription(), "test"))

    events = asyncio.run(_request_decoupled_events(app))

    assert [event["type"] for event in events] == ["stream_started", "partial", "completed"]
    assert events[1]["payload"] == {"text": "adapter text"}
    assert events[2]["payload"] == {"reason": "completed", "output": "adapter text", "audio_base64": ""}


def test_decoupled_get_receives_the_text_while_the_set_connection_is_open() -> None:
    async def run() -> list[dict]:
        app = _app_for(SttService(FakeTranscription(), "test"))
        transport = httpx.ASGITransport(app=app)

        async def body() -> AsyncIterator[bytes]:
            yield upload_body(b"\x01\x00")

        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            async with client.stream(
                "POST", "/process/stream/set", content=body(), headers=NDJSON
            ) as set_response:
                assert set_response.status_code == 200
                assert set_response.headers["x-status"] == "accepted"
                first_event = (await set_response.aiter_bytes().__anext__()).decode()
                assert _parse_sse_events(first_event)[0]["type"] == "stream_started"

                get_response = await client.get("/process/stream/get")
                assert get_response.status_code == 200
                return _parse_sse_events(get_response.text)

    events = asyncio.run(asyncio.wait_for(run(), timeout=5.0))

    assert [event["type"] for event in events] == ["stream_started", "partial", "completed"]
    assert events[1]["payload"] == {"text": "adapter text"}


def test_decoupled_get_stream_after_empty_engine_output_does_not_emit_empty_completed() -> None:
    app = _app_for(SttService(FakeTranscription(texts=[]), "test"))

    events = asyncio.run(_request_decoupled_events(app))

    _assert_event_shape(events[0], "stream_started", 1)
    assert len(events) == 1


def test_decoupled_get_stream_receives_two_completed_text_events_without_reconnecting() -> None:
    app = _app_for(SttService(FakeTranscription(texts=["first text", "second text"]), "test"))

    events = asyncio.run(_request_decoupled_events(app, b"\x01\x02\x03\x04", b"\x05\x06\x07\x08"))

    completed = [event for event in events if event["type"] == "completed"]
    assert [event["sequence"] for event in completed] == [3, 5]
    assert [event["payload"]["output"] for event in completed] == ["first text", "second text"]


def test_a_body_that_is_not_ndjson_events_is_a_415_on_both_stream_routes() -> None:
    app = _build_app(FakeService())

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return (
                await client.post("/process/stream/set", content=b"raw pcm"),
                await client.post("/process/stream", content=b"raw pcm"),
            )

    for response in asyncio.run(run()):
        assert response.status_code == 415
        assert "NDJSON" in response.json()["message"]


def test_stream_error_event_shape_is_valid() -> None:
    app = _build_app(FakeService(fail_process_stream_after_text=True))

    events = asyncio.run(_request_events(app, "POST", "/process/stream"))

    _assert_event_shape(events[0], "stream_started", 1)
    _assert_event_shape(events[3], "error", 4)
    assert events[3]["payload"] == {
        "code": "stream_failed",
        "message": "transcription backend unavailable",
        "recoverable": True,
    }


def test_stream_error_before_text_emits_no_chunks() -> None:
    app = _build_app(FakeService(fail_process_stream=True))

    events = asyncio.run(_request_events(app, "POST", "/process/stream"))

    _assert_event_shape(events[0], "stream_started", 1)
    _assert_event_shape(events[1], "error", 2)
    assert events[1]["payload"] == {
        "code": "stream_failed",
        "message": "transcription backend unavailable",
        "recoverable": True,
    }


def test_sequence_numbers_are_monotonic() -> None:
    app = _build_app(FakeService(process_items=["one", "two", "three"]))

    events = asyncio.run(_request_events(app, "POST", "/process/stream"))

    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
