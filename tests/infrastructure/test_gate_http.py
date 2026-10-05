"""The /gate routes over HTTP: the same shared stream as the main routes, but each completed event carries the audio."""

import asyncio
import base64
import json
from collections.abc import AsyncIterator

import httpx
from contracts.stream import schemas
from contracts.stream.codec import decode_event

from application.ports.outbound.transcription_port import TranscriptionPort, UtteranceTranscriptionPort
from application.services.stt_service import SttService
from composition_root.dependencies import stt_dependencies as deps
from domain.value_objects.stream_settings import StreamSettings
from domain.value_objects.utterance import Utterance


class Engine(UtteranceTranscriptionPort):
    def __init__(self, available: bool = True) -> None:
        self.available = available

    async def transcribe_stream(self, settings: StreamSettings, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[str]:
        async def texts() -> AsyncIterator[str]:
            async for chunk in audio_stream:
                if chunk:  # the HTTP client ends a streamed body with an empty chunk
                    yield "main " + chunk.decode()

        return texts()

    async def transcribe_utterances(self, settings: StreamSettings, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[Utterance]:
        async def utterances() -> AsyncIterator[Utterance]:
            async for chunk in audio_stream:
                if chunk:
                    yield Utterance("gate " + chunk.decode(), chunk)

        return utterances()

    async def transcribe_batch(self, audio_data: bytes, sample_rate: int) -> str:
        return "batch"

    def is_available(self) -> bool:
        return self.available


def _app(gate_available: bool = True, with_gate: bool = True):
    main = SttService(Engine(), "stt")
    gate = SttService(Engine(gate_available), "gate", with_audio=True) if with_gate else None
    return deps.new_http_app(main, "stt", gate)


async def _chunks(*items: bytes) -> AsyncIterator[bytes]:
    for item in items:
        yield item


async def _set_then_get(app, prefix: str, *audio: bytes) -> list[dict]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        async with client.stream("POST", f"{prefix}/process/stream/set", content=_chunks(*audio)) as response:
            assert response.status_code == 200
            async for _ in response.aiter_bytes():
                pass
        got = await client.get(f"{prefix}/process/stream/get", headers={"Accept": "application/x-ndjson"})
    assert got.status_code == 200
    return [json.loads(line) for line in got.text.splitlines() if line.strip()]


def test_the_gate_returns_the_audio_of_each_utterance_in_its_completed_event() -> None:
    events = asyncio.run(_set_then_get(_app(), "/gate", b"oblivion three oh six", b"hello"))

    completed = [e for e in events if e["type"] == "completed"]
    assert [e["payload"]["output"] for e in completed] == ["gate oblivion three oh six", "gate hello"]
    assert [base64.b64decode(e["payload"]["audio_base64"]) for e in completed] == [b"oblivion three oh six", b"hello"]
    for event in completed:  # and it is a valid event of the STT contract
        decoded = decode_event(json.dumps(event), schemas.STT_OUTBOUND)
        assert decoded.payload.audio_base64 == event["payload"]["audio_base64"]


def test_the_main_routes_never_carry_audio() -> None:
    events = asyncio.run(_set_then_get(_app(), "", b"hello"))

    (completed,) = [e for e in events if e["type"] == "completed"]
    assert completed["payload"] == {"reason": "completed", "output": "main hello", "audio_base64": ""}


def test_the_gate_and_the_main_stream_are_independent() -> None:
    app = _app()

    async def run() -> tuple[list[dict], list[dict]]:
        return await _set_then_get(app, "/gate", b"one"), await _set_then_get(app, "", b"two")

    gate_events, main_events = asyncio.run(run())

    assert [e["payload"]["output"] for e in gate_events if e["type"] == "completed"] == ["gate one"]
    assert [e["payload"]["output"] for e in main_events if e["type"] == "completed"] == ["main two"]


def test_there_are_no_gate_routes_unless_the_gate_is_enabled() -> None:
    async def run() -> int:
        transport = httpx.ASGITransport(app=_app(with_gate=False))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return (await client.get("/gate/available")).status_code

    assert asyncio.run(run()) == 404


def test_available_reports_the_gate_too_when_it_is_enabled() -> None:
    async def available(app, path: str) -> bool:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return (await client.get(path)).json()["data"]["is_available"]

    async def run() -> tuple[bool, bool, bool]:
        broken = _app(gate_available=False)
        return await available(broken, "/available"), await available(broken, "/gate/available"), await available(_app(), "/available")

    main_with_broken_gate, gate_itself, healthy = asyncio.run(run())

    assert (main_with_broken_gate, gate_itself, healthy) == (False, False, True)
