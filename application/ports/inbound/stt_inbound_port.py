from abc import ABC, abstractmethod

from application.dtos.inbound.process_batch_inbound import ProcessBatchInboundDTO
from application.dtos.inbound.process_stream_inbound import ProcessStreamInboundDTO
from application.dtos.inbound.set_stream_inbound import SetStreamInboundDTO
from application.dtos.outbound.batch_transcription_outbound import BatchTranscriptionOutboundDTO
from application.dtos.outbound.text_stream_outbound import TextStreamOutboundDTO


class SttInboundPort(ABC):
    """What every inbound adapter offers, whatever its transport (HTTP today; gRPC, a CLI, ... tomorrow).

    The same operations with DTOs and no transport types: an adapter decodes its own requests into these calls
    and encodes what they return. A new inbound adapter implements this port, so its functions are the same.
    """

    @abstractmethod
    def health(self) -> bool:
        """True while the adapter is serving."""

    @abstractmethod
    def is_available(self) -> bool:
        """True if everything behind the adapter is ready to accept requests."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the shared stream behind the adapter. Does nothing if none is active."""

    @abstractmethod
    async def process_stream(self, request: ProcessStreamInboundDTO) -> TextStreamOutboundDTO:
        """Transcribe a live stream of utterances; the text stream yields one item per utterance."""

    @abstractmethod
    async def set_stream(self, request: SetStreamInboundDTO) -> None:
        """Feed the shared stream and return when its utterances have ended."""

    @abstractmethod
    async def get_stream(self) -> TextStreamOutboundDTO:
        """The shared text stream. Raises NoActiveStream if ``set_stream`` was never called."""

    @abstractmethod
    async def process_batch(self, request: ProcessBatchInboundDTO) -> BatchTranscriptionOutboundDTO:
        """Transcribe a complete audio buffer."""
