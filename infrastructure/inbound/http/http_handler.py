"""HTTP inbound adapter: declares the endpoints and wires each one to its route. No request logic of its own."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from application.dtos.inbound.process_batch_inbound import ProcessBatchInboundDTO
from application.dtos.inbound.process_stream_inbound import ProcessStreamInboundDTO
from application.dtos.inbound.set_stream_inbound import SetStreamInboundDTO
from application.dtos.outbound.batch_transcription_outbound import BatchTranscriptionOutboundDTO
from application.dtos.outbound.text_stream_outbound import TextStreamOutboundDTO
from application.ports.inbound.stt_inbound_port import SttInboundPort
from application.ports.service.stt_service_port import SttServicePort
from infrastructure.inbound.http.routes.available import handle_available
from infrastructure.inbound.http.routes.get_stream import handle_get_stream
from infrastructure.inbound.http.routes.health import handle_health
from infrastructure.inbound.http.routes.process_batch import DEFAULT_SAMPLE_RATE, handle_process_batch
from infrastructure.inbound.http.routes.process_stream import handle_process_stream
from infrastructure.inbound.http.routes.set_stream import handle_set_stream
from infrastructure.inbound.http.routes.stop import handle_stop

GATE_PREFIX = "/gate"


class SttHandler(SttInboundPort):
    """The HTTP inbound adapter. It declares which endpoints exist and wires each to its function in ``routes/``;
    the request decoding, the answers and the error mapping live in ``helpers/``, ``response/`` and ``errors/``.
    Its operations are those of ``SttInboundPort`` (DTOs, no HTTP types) and the routes call them.

    The main handler has all the routes; the wake-phrase gate has its own, under ``/gate``, with only the shared
    stream (``set``/``get``), ``available`` and ``stop``, and its ``completed`` events carry the audio.

    The audio comes in as utterances, already cut by the microphone: STT does no silence detection."""

    def __init__(
        self,
        service: SttServicePort,
        *,
        prefix: str = "",
        include_audio: bool = False,
        gate: SttServicePort | None = None,
    ) -> None:
        self._service = service
        self._include_audio = include_audio
        self._gate = gate  # when the service also runs the gate, /available reports both
        self.router = APIRouter()
        self._register_routes(prefix)

    def _register_routes(self, prefix: str) -> None:
        inbound: SttInboundPort = self
        include_audio = self._include_audio
        add = self.router.add_api_route

        async def health() -> JSONResponse:
            return await handle_health(inbound)

        async def available() -> JSONResponse:
            return await handle_available(inbound)

        async def stop() -> JSONResponse:
            return await handle_stop(inbound)

        async def process_stream(request: Request) -> Response:
            return await handle_process_stream(request, inbound)

        async def set_stream(request: Request) -> Response:
            return await handle_set_stream(request, inbound)

        async def get_stream(request: Request) -> Response:
            return await handle_get_stream(request, inbound, include_audio)

        async def process_batch(request: Request, sample_rate: int = DEFAULT_SAMPLE_RATE) -> JSONResponse:
            return await handle_process_batch(request, sample_rate, inbound)

        if not prefix:
            add("/health", health, methods=["GET"], tags=["Health"])
        add(f"{prefix}/available", available, methods=["GET"])
        add(f"{prefix}/stop", stop, methods=["POST"])
        if not prefix:
            add("/process/stream", process_stream, methods=["POST"], response_model=None)
        add(f"{prefix}/process/stream/set", set_stream, methods=["POST"], response_model=None)
        add(f"{prefix}/process/stream/get", get_stream, methods=["GET"], response_model=None)
        if not prefix:
            add("/process/batch", process_batch, methods=["POST"])

    # --- SttInboundPort: the operations every inbound adapter offers --------------------------------

    def health(self) -> bool:
        return True

    def is_available(self) -> bool:
        return self._service.is_available() and (self._gate is None or self._gate.is_available())

    async def stop(self) -> None:
        await self._service.stop_stream()

    async def process_stream(self, request: ProcessStreamInboundDTO) -> TextStreamOutboundDTO:
        return await self._service.process_stream(request)

    async def set_stream(self, request: SetStreamInboundDTO) -> None:
        await self._service.set_stream(request)

    async def get_stream(self) -> TextStreamOutboundDTO:
        return await self._service.get_stream()

    async def process_batch(self, request: ProcessBatchInboundDTO) -> BatchTranscriptionOutboundDTO:
        return await self._service.process_batch(request)
