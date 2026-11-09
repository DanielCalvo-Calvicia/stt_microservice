"""Routes and error paths of SttHandler beyond the stream event contract."""

import asyncio
import json

import httpx
from fastapi import FastAPI
from shared_logging.testing import capture

from application.dtos.batch_transcription_outbound import BatchTranscriptionOutboundDTO
from application.dtos.process_batch_inbound import ProcessBatchInboundDTO
from application.errors import NoActiveStream
from application.services.stt_service import SttService
from composition_root.dependencies import stt_dependencies as deps
from domain.errors import InvalidAudioUtterance
from infrastructure.inbound.http.http_handler import SttHandler
from infrastructure.outbound.openai_whisper.openai_whisper_transcription import (
    OpenAIWhisperTranscription,
)
from tests.infrastructure.test_http_handler import NDJSON, FakeService, upload_body
from tests.infrastructure.test_transcription_engines import (
    FAKE_KEY,
    _failing_openai,
    _wrong_key_error,
)


def _call(service: FakeService, method: str, path: str, **kwargs) -> httpx.Response:
    async def run() -> httpx.Response:
        app = FastAPI()
        app.include_router(SttHandler(service).router)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(run())


def test_health_and_availability():
    health = _call(FakeService(), "GET", "/health").json()
    assert health["status"] == "success" and health["action"] == "health_check"

    available = _call(FakeService(), "GET", "/available").json()
    assert available["data"] == {"is_available": True, "reason": None} and available["action"] == "check_availability"


def test_stop_reports_success():
    body = _call(FakeService(), "POST", "/stop").json()
    assert body["status"] == "success" and body["action"] == "stop_stream"


def test_get_stream_before_set_stream_is_a_404_with_the_error_text():
    class NoStream(FakeService):
        async def get_stream(self):
            raise NoActiveStream("No active stream has been set")

    response = _call(NoStream(), "GET", "/process/stream/get")

    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "No active stream has been set"
    assert body["data"] == "No active stream has been set"


def test_batch_returns_the_transcribed_text():
    class Batch(FakeService):
        async def process_batch(self, request: ProcessBatchInboundDTO):
            return BatchTranscriptionOutboundDTO(
                text=f"{len(request.audio_data)} bytes @ {request.sample_rate}"
            )

    response = _call(Batch(), "POST", "/process/batch?sample_rate=8000", content=b"abcd")

    assert response.status_code == 200
    assert response.json()["data"] == {"text": "4 bytes @ 8000", "confidence": None}


def test_batch_with_an_empty_body_is_a_400():
    response = _call(FakeService(), "POST", "/process/batch", content=b"")

    assert response.status_code == 400
    assert response.json()["message"] == "No audio data provided"


def test_batch_failure_is_a_500_envelope():
    class Broken(FakeService):
        async def process_batch(self, request):
            raise RuntimeError("engine offline")

    response = _call(Broken(), "POST", "/process/batch", content=b"ab")

    assert response.status_code == 500
    assert response.json()["message"] == "Failed to process batch: engine offline"


def test_an_invalid_utterance_is_a_422_envelope_not_a_crash():
    class Rejecting(FakeService):
        async def process_stream(self, request):
            raise InvalidAudioUtterance("sample_rate must be positive")

    response = _call(
        Rejecting(), "POST", "/process/stream", content=upload_body(b"ab"), headers=NDJSON
    )

    assert response.status_code == 422
    assert "must be positive" in response.json()["message"]


def test_a_body_that_is_not_ndjson_is_rejected_up_front_with_a_415():
    response = _call(FakeService(), "POST", "/process/stream/set", content=b"raw pcm")

    assert response.status_code == 415
    assert response.json()["action"] == "set_stream"


# --- a wrong OpenAI key must not come back in part, in an answer, an event or a log (T-01.7) ---

FIXED_FAILURE = "OpenAI request failed: AuthenticationError (HTTP 401)"


def _openai_app(monkeypatch) -> FastAPI:
    """The real app and the real OpenAI engine; only the client is one the API refuses."""
    _failing_openai(monkeypatch, _wrong_key_error())
    service = SttService(OpenAIWhisperTranscription(FAKE_KEY), "stt")
    return deps.new_http_app(service, "stt", None)


def _ask(app: FastAPI, *requests: tuple[str, str, dict]) -> list[httpx.Response]:
    async def run() -> list[httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return [
                await client.request(method, path, **kwargs) for method, path, kwargs in requests
            ]

    return asyncio.run(run())


def _nothing_of_the_key(text: str) -> None:
    assert "sk-" not in text and FAKE_KEY not in text
    assert "Incorrect API key" not in text and "fake" not in text


def test_a_wrong_openai_key_is_a_500_with_a_fixed_message_in_the_batch_and_the_log(monkeypatch):
    app = _openai_app(monkeypatch)

    with capture("stt") as logs:
        (response,) = _ask(
            app, ("POST", "/process/batch?sample_rate=16000", {"content": b"\x01\x00" * 100})
        )

    assert response.status_code == 500
    body = response.json()
    assert body["message"] == f"Failed to process batch: {FIXED_FAILURE}"
    assert body["data"] == FIXED_FAILURE
    _nothing_of_the_key(response.text)
    logged = json.dumps(logs.records, default=str)
    assert FIXED_FAILURE in logged  # the failure is logged, with the fixed text
    _nothing_of_the_key(logged)


def test_a_wrong_openai_key_is_a_fixed_message_in_the_error_event_of_the_stream(monkeypatch):
    app = _openai_app(monkeypatch)

    with capture("stt") as logs:
        sent, got = _ask(
            app,
            ("POST", "/process/stream/set", {"content": upload_body(b"hello!"), "headers": NDJSON}),
            ("GET", "/process/stream/get", {"headers": {"Accept": "application/x-ndjson"}}),
        )

    assert sent.status_code == 200 and got.status_code == 200
    events = [json.loads(line) for line in got.text.splitlines() if line.strip()]
    (error,) = [event for event in events if event["type"] == "error"]
    assert error["payload"]["code"] == "stream_failed"
    assert error["payload"]["message"] == FIXED_FAILURE
    _nothing_of_the_key(got.text)
    _nothing_of_the_key(json.dumps(logs.records, default=str))
