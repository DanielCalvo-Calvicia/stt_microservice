from abc import ABC, abstractmethod

from application.dtos.services_dtos import (
    ProcessStreamRequestDto,
    ProcessStreamResponseDto,
    ProcessBatchRequestDto,
    ProcessBatchResponseDto,
    STTAvailabilityRequestDto,
    STTAvailabilityResponseDto,
)


class ServicePort(ABC):
    @abstractmethod
    async def process_stream(self, request: ProcessStreamRequestDto) -> ProcessStreamResponseDto:
        """Orchestrate real-time stream processing."""
        pass

    @abstractmethod
    async def process_batch(self, request: ProcessBatchRequestDto) -> ProcessBatchResponseDto:
        """Orchestrate batch audio processing."""
        pass

    @abstractmethod
    async def is_available(self, request: STTAvailabilityRequestDto) -> STTAvailabilityResponseDto:
        """Check STT service availability."""
        pass
