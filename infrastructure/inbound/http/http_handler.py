"""HTTP inbound adapter: decode -> call the inbound port -> encode. No business rules."""

import time
from collections.abc import AsyncIterator, Callable
from typing import Any

from contracts.api.microservices.common.availability import AvailabilityResponse
from contracts.api.microservices.common.health_check import HealthCheckResponse
from contracts.api.microservices.stt.process_batch import STTProcessBatchResponse
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse, Response, StreamingResponse
from shared_logging import get_logger

from application.dtos.process_batch_inbound import ProcessBatchInboundDTO
from application.dtos.process_stream_inbound import ProcessStreamInboundDTO
from application.dtos.set_stream_inbound import SetStreamInboundDTO
from application.errors import NoActiveStream, StreamSettingsMismatch
from application.ports.inbound.stt_transcription_port import SttTranscriptionPort
from domain.value_objects.stream_settings import StreamSettings
from infrastructure.inbound.http.http_envelope import failure, failure_message, success
from infrastructure.inbound.http.input_stream_response import InputStreamResponse
from infrastructure.inbound.http.ndjson_audio_input import ndjson_audio_stream
from infrastructure.inbound.http.stream_events import (
    Formatter,
    ndjson_format,
    sse_format,
    text_event_stream,
)

logger = get_logger(__name__)

_DEFAULTS = StreamSettings()
_NDJSON = "application/x-ndjson"
_SSE = "text/event-stream"
_GET_HEARTBEAT_SECONDS = 15.0


def _wants_ndjson(request: Request) -> bool:
    return _NDJSON in request.headers.get("accept", "").lower()


def _is_ndjson_request(request: Request) -> bool:
    return _NDJSON in request.headers.get("content-type", "").lower()


def _stream_headers(action: str, status_text: str, message: str) -> dict[str, str]:
    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Action": action,
        "X-Status": status_text,
        "X-Message": message,
        "X-Timestamp": str(time.time()),
    }


async def _request_body_chunks(request: Request) -> AsyncIterator[bytes]:
    async for chunk in request.stream():
        logger.debug("Received stream chunk", bytes=len(chunk))
        yield chunk


class SttHandler:
    def __init__(self, port: SttTranscriptionPort) -> None:
        self._port = port
        self.router = APIRouter()
        add = self.router.add_api_route
        add("/health", self.handle_health, methods=["GET"], tags=["Health"])
        add("/available", self.handle_available, methods=["GET"])
        add("/stop", self.handle_stop, methods=["POST"])
        add("/process/stream", self.handle_process_stream, methods=["POST"], response_model=None)
        add("/process/stream/set", self.handle_set_stream, methods=["POST"], response_model=None)
        add("/process/stream/get", self.handle_get_stream, methods=["GET"], response_model=None)
        add("/process/batch", self.handle_process_batch, methods=["POST"])

    async def handle_health(self) -> JSONResponse:
        return success("health_check", "Service is healthy", HealthCheckResponse(healthy=True))

    async def handle_available(self) -> JSONResponse:
        try:
            available = self._port.is_available()
        except Exception as error:
            return failure("check_availability", "Failed to check availability", error)
        return success(
            "check_availability",
            "Availability checked successfully",
            AvailabilityResponse(is_available=available),
        )

    async def handle_stop(self) -> JSONResponse:
        try:
            await self._port.stop_stream()
        except Exception as error:
            return failure("stop_stream", "Failed to stop stream", error)
        return success("stop_stream", "Stream stopped successfully")

    async def handle_process_stream(
        self,
        request: Request,
        sample_rate: int = _DEFAULTS.sample_rate,
        chunk_size: int = _DEFAULTS.chunk_size,
        silence_threshold: int = _DEFAULTS.silence_threshold,
        silence_limit_seconds: float = _DEFAULTS.silence_limit_seconds,
    ) -> Response:
        try:
            result = await self._port.process_stream(
                ProcessStreamInboundDTO(
                    audio_stream=_request_body_chunks(request),
                    sample_rate=sample_rate,
                    chunk_size=chunk_size,
                    silence_threshold=silence_threshold,
                    silence_limit_seconds=silence_limit_seconds,
                )
            )
        except Exception as error:
            return failure("process_stream", "Failed to process stream", error)
        return StreamingResponse(
            text_event_stream(result.text_stream),
            media_type=_SSE,
            status_code=status.HTTP_200_OK,
            headers=_stream_headers("process_stream", "success", "Stream processed successfully"),
        )

    async def handle_set_stream(
        self,
        request: Request,
        sample_rate: int = _DEFAULTS.sample_rate,
        chunk_size: int = _DEFAULTS.chunk_size,
        silence_threshold: int = _DEFAULTS.silence_threshold,
        silence_limit_seconds: float = _DEFAULTS.silence_limit_seconds,
    ) -> Response:
        try:
            audio_stream: AsyncIterator[Any] = _request_body_chunks(request)
            if _is_ndjson_request(request):
                logger.info("Set stream using NDJSON audio event input")
                audio_stream = ndjson_audio_stream(
                    audio_stream,
                    StreamSettings(
                        sample_rate=sample_rate,
                        chunk_size=chunk_size,
                        silence_threshold=silence_threshold,
                        silence_limit_seconds=silence_limit_seconds,
                    ),
                )
            dto = SetStreamInboundDTO(
                audio_stream=audio_stream,
                sample_rate=sample_rate,
                chunk_size=chunk_size,
                silence_threshold=silence_threshold,
                silence_limit_seconds=silence_limit_seconds,
            )
        except Exception as error:
            return failure("set_stream", "Failed to set stream", error)

        async def run_set_stream() -> None:
            await self._port.set_stream(dto)
            logger.info("Set stream completed")

        formatter, media_type = self._output_format(request)
        return InputStreamResponse(
            run_set_stream,
            formatter=formatter,
            media_type=media_type,
            status_code=status.HTTP_200_OK,
            headers=_stream_headers(
                "set_stream", "accepted", "Input stream connection established"
            ),
        )

    async def handle_get_stream(
        self,
        request: Request,
        sample_rate: int | None = None,
        chunk_size: int | None = None,
        silence_threshold: int | None = None,
        silence_limit_seconds: float | None = None,
    ) -> Response:
        """Read the transcripts of the stream set with ``/process/stream/set``.

        The stream's settings were fixed by ``set``; any of them repeated here must match.
        """
        try:
            self._check_matches_active_settings(
                sample_rate=sample_rate,
                chunk_size=chunk_size,
                silence_threshold=silence_threshold,
                silence_limit_seconds=silence_limit_seconds,
            )
            result = await self._port.get_stream()
        except NoActiveStream as error:
            logger.warning("Get stream rejected", error=error)
            return failure_message("get_stream", str(error), status.HTTP_404_NOT_FOUND, str(error))
        except Exception as error:
            return failure("get_stream", "Failed to get stream", error)

        formatter, media_type = self._output_format(request)
        return StreamingResponse(
            text_event_stream(
                result.text_stream,
                formatter=formatter,
                emit_empty_completion_on_end=False,
                heartbeat_interval_seconds=_GET_HEARTBEAT_SECONDS,
            ),
            media_type=media_type,
            status_code=status.HTTP_200_OK,
            headers=_stream_headers("get_stream", "success", "Stream retrieved successfully"),
        )

    async def handle_process_batch(
        self, request: Request, sample_rate: int = _DEFAULTS.sample_rate
    ) -> JSONResponse:
        try:
            audio_data = await request.body()
            if not audio_data:
                logger.warning("Batch request rejected: empty audio body")
                return failure_message(
                    "process_batch",
                    "No audio data provided",
                    status.HTTP_400_BAD_REQUEST,
                    "No audio data provided",
                )
            result = await self._port.process_batch(
                ProcessBatchInboundDTO(audio_data=audio_data, sample_rate=sample_rate)
            )
        except Exception as error:
            return failure("process_batch", "Failed to process batch", error)
        return success(
            "process_batch",
            "Audio processed successfully",
            STTProcessBatchResponse(text=result.text),
        )

    def _check_matches_active_settings(self, **given: float | None) -> None:
        active = self._port.current_settings()
        if active is None:
            return  # nothing set yet: get_stream reports NoActiveStream
        for name, value in given.items():
            if value is not None and value != getattr(active, name):
                raise StreamSettingsMismatch(
                    f"{name}={value} differs from the active stream's {name}={getattr(active, name)}"
                )

    @staticmethod
    def _output_format(request: Request) -> tuple[Formatter, str]:
        if _wants_ndjson(request):
            return ndjson_format, _NDJSON
        return sse_format, _SSE
