from application.ports.service_port import ServicePort
from application.ports.adapter_outbound_port import AdapterOutboundPort
from runtime.logger import get_logger

from application.dtos.services_dtos import (
    ProcessStreamRequestDto as ServiceStreamRequest,
    ProcessStreamResponseDto as ServiceStreamResponse,
    ProcessBatchRequestDto as ServiceBatchRequest,
    ProcessBatchResponseDto as ServiceBatchResponse,
    STTAvailabilityRequestDto as ServiceAvailabilityRequest,
    STTAvailabilityResponseDto as ServiceAvailabilityResponse,
)

from application.dtos.mapper.service_to_adapter_outbound import (
    map_service_to_outbound_stream_request,
    map_service_to_outbound_batch_request,
    map_service_to_outbound_availability_request,
)
from application.dtos.mapper.adapter_outbound_to_service import (
    map_outbound_to_service_stream_response,
    map_outbound_to_service_batch_response,
    map_outbound_to_service_availability_response,
)

logger = get_logger(__name__)


class STTService(ServicePort):
    def __init__(self, name: str, outbound_port: AdapterOutboundPort):
        self.name = name
        self.outbound_port = outbound_port
        logger.info("STTService '%s' initialized with outbound adapter %s.", name, type(outbound_port).__name__)

    async def process_stream(self, request: ServiceStreamRequest) -> ServiceStreamResponse:
        logger.info(
            "STTService '%s' processing stream: sample_rate=%s chunk_size=%s silence_threshold=%s silence_limit_seconds=%s.",
            self.name,
            request.sample_rate,
            request.chunk_size,
            request.silence_threshold,
            request.silence_limit_seconds,
        )
        outbound_req = map_service_to_outbound_stream_request(request)
        outbound_res = await self.outbound_port.process_stream(outbound_req)
        logger.info("STTService '%s' received outbound stream response.", self.name)
        return map_outbound_to_service_stream_response(outbound_res)

    async def process_batch(self, request: ServiceBatchRequest) -> ServiceBatchResponse:
        logger.info(
            "STTService '%s' processing batch: bytes=%s sample_rate=%s.",
            self.name,
            len(request.audio_data),
            request.sample_rate,
        )
        outbound_req = map_service_to_outbound_batch_request(request)
        outbound_res = await self.outbound_port.process_batch(outbound_req)
        logger.info("STTService '%s' received outbound batch response: text_length=%s.", self.name, len(outbound_res.text))
        return map_outbound_to_service_batch_response(outbound_res)

    async def is_available(self, request: ServiceAvailabilityRequest) -> ServiceAvailabilityResponse:
        logger.info("STTService '%s' checking outbound adapter availability.", self.name)
        outbound_req = map_service_to_outbound_availability_request(request)
        outbound_res = await self.outbound_port.is_available(outbound_req)
        logger.info("STTService '%s' availability result: %s.", self.name, outbound_res.is_available)
        return map_outbound_to_service_availability_response(outbound_res)
