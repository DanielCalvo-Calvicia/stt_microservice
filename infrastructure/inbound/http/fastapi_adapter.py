import time
from typing import AsyncIterator, Any

from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from application.ports.adapter_inbound_port import AdapterInboundPort
from application.ports.service_port import ServicePort

from application.dtos.adapter_inbound_dtos import (
    ProcessStreamRequestDto,
    ProcessStreamResponseDto,
    SetStreamRequestDto,
    SetStreamResponseDto,
    GetStreamRequestDto,
    GetStreamResponseDto,
    ProcessBatchRequestDto,
    ProcessBatchResponseDto,
    STTAvailabilityRequestDto,
    STTAvailabilityResponseDto,
    InitInboundAdapterDto,
)

from infrastructure.inbound.http.voice_stream_autoloader import VoiceStreamAutoloader

from application.dtos.mapper.adapter_inbound_to_service import (
    map_inbound_to_service_stream_request,
    map_inbound_to_service_set_stream_request,
    map_inbound_to_service_get_stream_request,
    map_inbound_to_service_batch_request,
    map_inbound_to_service_availability_request,
)

from application.dtos.mapper.service_to_adapter_inbound import (
    map_service_to_inbound_stream_response,
    map_service_to_inbound_set_stream_response,
    map_service_to_inbound_get_stream_response,
    map_service_to_inbound_batch_response,
    map_service_to_inbound_availability_response,
)
from runtime.logger import get_logger


logger = get_logger(__name__)


class FastApiAdapter(AdapterInboundPort):
    def __init__(self, service_port: ServicePort, app: FastAPI, config: InitInboundAdapterDto):
        self.service_port = service_port
        self.app = app
        logger.info("Initializing FastApiAdapter.")
        
        self.autoloader = None
        if config.autoload_voice_stream_url:
            logger.info("Configuring VoiceStreamAutoloader for %s.", config.autoload_voice_stream_url)
            self.autoloader = VoiceStreamAutoloader(config.autoload_voice_stream_url, self)
        else:
            logger.info("VoiceStreamAutoloader is disabled.")

        self.register_routes(self.app)

    def register_routes(self, app: FastAPI):
        logger.info("Registering FastAPI routes.")

        @app.get("/health", tags=["Health"])
        async def health_check():
            logger.info("HTTP GET /health received.")
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "action": "health_check",
                    "status": "success",
                    "status_code": status.HTTP_200_OK,
                    "message": "Service is healthy",
                    "timestamp": time.time(),
                    "data": None
                }
            )

        @app.get("/available", status_code=status.HTTP_200_OK)
        async def handle_check_availability():
            logger.info("HTTP GET /available received.")
            try:
                request_dto = STTAvailabilityRequestDto()
                response = await self.is_available(request_dto)
                logger.info("HTTP GET /available completed: is_available=%s.", response.is_available)
                http_response = JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content={
                        "action": "check_availability",
                        "status": "success",
                        "status_code": status.HTTP_200_OK,
                        "message": "Availability checked successfully",
                        "timestamp": time.time(),
                        "data": response.is_available
                    }
                )
                return http_response
            except Exception as e:
                logger.exception("HTTP GET /available failed.")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "action": "check_availability",
                        "status": "error",
                        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                        "message": f"Failed to check availability: {str(e)}",
                        "timestamp": time.time(),
                        "data": str(e)
                    }
                )

        @app.post("/process/stream", status_code=status.HTTP_200_OK)
        async def handle_process_stream(
            request: Request,
            sample_rate: int = 16000,
            chunk_size: int = 1024,
            silence_threshold: int = 150,
            silence_limit_seconds: float = 2.0,
        ):
            logger.info(
                "HTTP POST /process/stream received: sample_rate=%s chunk_size=%s silence_threshold=%s silence_limit_seconds=%s.",
                sample_rate,
                chunk_size,
                silence_threshold,
                silence_limit_seconds,
            )
            try:
                async def request_stream_generator() -> AsyncIterator[bytes]:
                    async for chunk in request.stream():
                        logger.debug("Received stream chunk: bytes=%s.", len(chunk))
                        yield chunk

                request_dto = ProcessStreamRequestDto(
                    audio_stream=request_stream_generator(),
                    sample_rate=sample_rate,
                    chunk_size=chunk_size,
                    silence_threshold=silence_threshold,
                    silence_limit_seconds=silence_limit_seconds,
                )

                response = await self.process_stream(request_dto)
                logger.info("HTTP POST /process/stream returning SSE response.")

                async def text_stream_generator() -> AsyncIterator[str]:
                    async for text in response.text_stream:
                        logger.info("Streaming transcription event: text_length=%s.", len(text))
                        yield f"data: {text}\n\n"

                http_response = StreamingResponse(
                    text_stream_generator(),
                    media_type="text/event-stream",
                    status_code=status.HTTP_200_OK,
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Action": "process_stream",
                        "X-Status": "success",
                        "X-Message": "Stream processed successfully",
                        "X-Timestamp": str(time.time()),
                    }
                )
                return http_response
            except Exception as e:
                logger.exception("HTTP POST /process/stream failed.")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "action": "process_stream",
                        "status": "error",
                        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                        "message": f"Failed to process stream: {str(e)}",
                        "timestamp": time.time(),
                        "data": str(e)
                    }
                )

        @app.post("/process/stream/set", status_code=status.HTTP_200_OK)
        async def handle_set_stream(
            request: Request,
            sample_rate: int = 16000,
            chunk_size: int = 1024,
            silence_threshold: int = 150,
            silence_limit_seconds: float = 2.0,
        ):
            logger.info(
                "HTTP POST /process/stream/set received: sample_rate=%s chunk_size=%s silence_threshold=%s silence_limit_seconds=%s.",
                sample_rate,
                chunk_size,
                silence_threshold,
                silence_limit_seconds,
            )
            try:
                async def request_stream_generator() -> AsyncIterator[bytes]:
                    async for chunk in request.stream():
                        logger.debug("Received decoupled stream chunk: bytes=%s.", len(chunk))
                        yield chunk

                request_dto = SetStreamRequestDto(
                    audio_stream=request_stream_generator(),
                    sample_rate=sample_rate,
                    chunk_size=chunk_size,
                    silence_threshold=silence_threshold,
                    silence_limit_seconds=silence_limit_seconds,
                )

                response = await self.set_stream(request_dto)
                logger.info("HTTP POST /process/stream/set completed: accepted=%s.", response.accepted)

                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content={
                        "action": "set_stream",
                        "status": "success",
                        "status_code": status.HTTP_200_OK,
                        "message": "Stream accepted successfully",
                        "timestamp": time.time(),
                        "data": {"accepted": response.accepted}
                    }
                )
            except Exception as e:
                logger.exception("HTTP POST /process/stream/set failed.")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "action": "set_stream",
                        "status": "error",
                        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                        "message": f"Failed to set stream: {str(e)}",
                        "timestamp": time.time(),
                        "data": str(e)
                    }
                )

        @app.get("/process/stream/get", status_code=status.HTTP_200_OK)
        async def handle_get_stream():
            logger.info("HTTP GET /process/stream/get received.")
            try:
                request_dto = GetStreamRequestDto()
                response = await self.get_stream(request_dto)
                logger.info("HTTP GET /process/stream/get returning SSE response.")

                async def text_stream_generator() -> AsyncIterator[str]:
                    async for text in response.text_stream:
                        logger.info("Streaming decoupled transcription event: text_length=%s.", len(text))
                        yield f"data: {text}\n\n"

                return StreamingResponse(
                    text_stream_generator(),
                    media_type="text/event-stream",
                    status_code=status.HTTP_200_OK,
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Action": "get_stream",
                        "X-Status": "success",
                        "X-Message": "Stream retrieved successfully",
                        "X-Timestamp": str(time.time()),
                    }
                )
            except RuntimeError as e:
                logger.warning("HTTP GET /process/stream/get rejected: %s.", e)
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={
                        "action": "get_stream",
                        "status": "error",
                        "status_code": status.HTTP_404_NOT_FOUND,
                        "message": str(e),
                        "timestamp": time.time(),
                        "data": str(e)
                    }
                )
            except Exception as e:
                logger.exception("HTTP GET /process/stream/get failed.")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "action": "get_stream",
                        "status": "error",
                        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                        "message": f"Failed to get stream: {str(e)}",
                        "timestamp": time.time(),
                        "data": str(e)
                    }
                )

        @app.post("/process/batch", status_code=status.HTTP_200_OK)
        async def handle_process_batch(
            request: Request,
            sample_rate: int = 16000,
        ):
            logger.info("HTTP POST /process/batch received: sample_rate=%s.", sample_rate)
            try:
                audio_data = await request.body()
                logger.info("HTTP POST /process/batch body read: bytes=%s.", len(audio_data))
                if not audio_data:
                    logger.warning("HTTP POST /process/batch rejected empty audio body.")
                    raise HTTPException(status_code=400, detail="No audio data provided")

                request_dto = ProcessBatchRequestDto(
                    audio_data=audio_data,
                    sample_rate=sample_rate,
                )

                response = await self.process_batch(request_dto)
                logger.info("HTTP POST /process/batch completed: text_length=%s.", len(response.text))

                http_response = JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content={
                        "action": "process_batch",
                        "status": "success",
                        "status_code": status.HTTP_200_OK,
                        "message": "Audio processed successfully",
                        "timestamp": time.time(),
                        "data": {"text": response.text}
                    }
                )
                return http_response
            except Exception as e:
                logger.exception("HTTP POST /process/batch failed.")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "action": "process_batch",
                        "status": "error",
                        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                        "message": f"Failed to process batch: {str(e)}",
                        "timestamp": time.time(),
                        "data": str(e)
                    }
                )

        # Routes are registered above
        logger.info("FastAPI routes registered.")

    def start_autoload(self) -> None:
        if self.autoloader:
            logger.info("Starting VoiceStreamAutoloader.")
            self.autoloader.start()
        else:
            logger.info("Autoload start requested, but autoloader is not configured.")

    async def stop_autoload(self) -> None:
        if self.autoloader:
            logger.info("Stopping VoiceStreamAutoloader.")
            await self.autoloader.stop()
        else:
            logger.info("Autoload stop requested, but autoloader is not configured.")

    @property
    def get_app(self) -> Any:
        logger.debug("Returning FastAPI app instance.")
        return self.app

    async def process_stream(self, request: ProcessStreamRequestDto) -> ProcessStreamResponseDto:
        logger.info("Inbound adapter processing stream request.")
        service_request_dto = map_inbound_to_service_stream_request(request)
        service_response_dto = await self.service_port.process_stream(service_request_dto)
        adapter_response_dto = map_service_to_inbound_stream_response(service_response_dto)
        logger.info("Inbound adapter stream request mapped back to response.")
        return adapter_response_dto

    async def set_stream(self, request: SetStreamRequestDto) -> SetStreamResponseDto:
        logger.info("Inbound adapter setting shared stream.")
        service_request_dto = map_inbound_to_service_set_stream_request(request)
        service_response_dto = await self.service_port.set_stream(service_request_dto)
        adapter_response_dto = map_service_to_inbound_set_stream_response(service_response_dto)
        logger.info("Inbound adapter set stream completed: accepted=%s.", adapter_response_dto.accepted)
        return adapter_response_dto

    async def get_stream(self, request: GetStreamRequestDto) -> GetStreamResponseDto:
        logger.info("Inbound adapter getting shared stream.")
        service_request_dto = map_inbound_to_service_get_stream_request(request)
        service_response_dto = await self.service_port.get_stream(service_request_dto)
        adapter_response_dto = map_service_to_inbound_get_stream_response(service_response_dto)
        logger.info("Inbound adapter get stream mapped back to response.")
        return adapter_response_dto

    async def process_batch(self, request: ProcessBatchRequestDto) -> ProcessBatchResponseDto:
        logger.info("Inbound adapter processing batch request: bytes=%s sample_rate=%s.", len(request.audio_data), request.sample_rate)
        service_request_dto = map_inbound_to_service_batch_request(request)
        service_response_dto = await self.service_port.process_batch(service_request_dto)
        adapter_response_dto = map_service_to_inbound_batch_response(service_response_dto)
        logger.info("Inbound adapter batch request completed: text_length=%s.", len(adapter_response_dto.text))
        return adapter_response_dto

    async def is_available(self, request: STTAvailabilityRequestDto) -> STTAvailabilityResponseDto:
        logger.info("Inbound adapter checking availability.")
        service_request_dto = map_inbound_to_service_availability_request(request)
        service_response_dto = await self.service_port.is_available(service_request_dto)
        adapter_response_dto = map_service_to_inbound_availability_response(service_response_dto)
        logger.info("Inbound adapter availability result: %s.", adapter_response_dto.is_available)
        return adapter_response_dto
