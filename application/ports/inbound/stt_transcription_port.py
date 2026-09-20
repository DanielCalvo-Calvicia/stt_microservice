from abc import ABC, abstractmethod

from domain.value_objects.stream_settings import StreamSettings

from application.dtos.batch_transcription_outbound import BatchTranscriptionOutboundDTO
from application.dtos.process_batch_inbound import ProcessBatchInboundDTO
from application.dtos.process_stream_inbound import ProcessStreamInboundDTO
from application.dtos.set_stream_inbound import SetStreamInboundDTO
from application.dtos.text_stream_outbound import TextStreamOutboundDTO


class SttTranscriptionPort(ABC):
    """What the outside world may ask of the application."""

    @abstractmethod
    async def process_stream(self, request: ProcessStreamInboundDTO) -> TextStreamOutboundDTO:
        """Transcribe a live audio stream; the text stream yields one item per utterance."""

    @abstractmethod
    async def set_stream(self, request: SetStreamInboundDTO) -> None:
        """Feed the shared stream and return when its audio has ended.

        A new call replaces the previous one. Read the text with ``get_stream``.
        """

    @abstractmethod
    async def get_stream(self) -> TextStreamOutboundDTO:
        """The shared text stream. Raises NoActiveStream if ``set_stream`` was never called."""

    def current_settings(self) -> StreamSettings | None:
        """The settings the shared stream was set with, or None before any ``set_stream``."""
        return None

    @abstractmethod
    async def stop_stream(self) -> None:
        """Stop the shared stream. Does nothing if none is active."""

    @abstractmethod
    async def process_batch(self, request: ProcessBatchInboundDTO) -> BatchTranscriptionOutboundDTO:
        """Transcribe a complete audio buffer."""

    @abstractmethod
    def is_available(self) -> bool:
        """True if the transcription engine is ready to accept requests."""
