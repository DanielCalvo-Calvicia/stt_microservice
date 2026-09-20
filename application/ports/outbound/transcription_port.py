from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from domain.value_objects.stream_settings import StreamSettings


class TranscriptionPort(ABC):
    """What the application needs from a speech-to-text engine."""

    @abstractmethod
    async def transcribe_stream(
        self, settings: StreamSettings, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[str]:
        """Split ``audio_stream`` (16-bit mono PCM) into utterances and yield each one's text.

        The audio is consumed as the returned iterator is consumed. A failure of the engine or
        of ``audio_stream`` surfaces while iterating.
        """

    @abstractmethod
    async def transcribe_batch(self, audio_data: bytes, sample_rate: int) -> str:
        """Transcribe one complete 16-bit mono PCM buffer."""

    @abstractmethod
    def is_available(self) -> bool:
        """True if the engine is loaded/configured."""
