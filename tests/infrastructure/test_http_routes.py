"""Routes and error paths of SttHandler beyond the stream event contract."""

import asyncio

import httpx
from fastapi import FastAPI

from application.dtos.batch_transcription_outbound import BatchTranscriptionOutboundDTO
from application.dtos.process_batch_inbound import ProcessBatchInboundDTO
from application.errors import NoActiveStream
from domain.errors import InvalidStreamSettings
from infrastructure.inbound.http.http_handler import SttHandler
from tests.infrastructure.test_http_handler import FakeService


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


def test_invalid_stream_settings_are_a_422_envelope_not_a_crash():
    class Rejecting(FakeService):
        async def process_stream(self, request):
            raise InvalidStreamSettings("sample_rate and chunk_size must be positive")

    response = _call(Rejecting(), "POST", "/process/stream?chunk_size=0", content=b"ab")

    assert response.status_code == 422
    assert "must be positive" in response.json()["message"]


def test_ndjson_set_stream_with_invalid_settings_is_rejected_up_front():
    response = _call(
        FakeService(),
        "POST",
        "/process/stream/set?chunk_size=0",
        content=b"{}\n",
        headers={"Content-Type": "application/x-ndjson"},
    )

    assert response.status_code == 422
    assert response.json()["action"] == "set_stream"
