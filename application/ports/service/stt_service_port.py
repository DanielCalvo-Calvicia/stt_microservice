from abc import ABC, abstractmethod

from application.dtos.inbound.process_batch_inbound import ProcessBatchInboundDTO
from application.dtos.inbound.process_stream_inbound import ProcessStreamInboundDTO
from application.dtos.inbound.set_stream_inbound import SetStreamInboundDTO
from application.dtos.outbound.batch_transcription_outbound import BatchTranscriptionOutboundDTO
from application.dtos.outbound.text_stream_outbound import TextStreamOutboundDTO


class SttServicePort(ABC):
    """The service's own port: the speech-to-text use cases. ``SttService`` implements it; the inbound adapters
    call it (through the inbound port); nothing else in the application knows the concrete service."""

    @abstractmethod
    async def process_stream(self, request: ProcessStreamInboundDTO) -> TextStreamOutboundDTO:
        """Transcribe a live stream of utterances; the text stream yields one item per utterance."""

    @abstractmethod
    async def set_stream(self, request: SetStreamInboundDTO) -> None:
        """Feed the shared stream and return when its utterances have ended.

        A new call replaces the previous one. Read the text with ``get_stream``.
        """

    @abstractmethod
    async def get_stream(self) -> TextStreamOutboundDTO:
        """The shared text stream. Raises NoActiveStream if ``set_stream`` was never called."""

    @abstractmethod
    async def stop_stream(self) -> None:
        """Stop the shared stream. Does nothing if none is active."""

    @abstractmethod
    async def process_batch(self, request: ProcessBatchInboundDTO) -> BatchTranscriptionOutboundDTO:
        """Transcribe a complete audio buffer."""

    @abstractmethod
    def is_available(self) -> bool:
        """True if the transcription engine is ready to accept requests."""
