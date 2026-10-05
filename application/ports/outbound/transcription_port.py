from abc import ABC, abstractmethod


class TranscriptionPort(ABC):
    """What the application needs from a speech-to-text engine: the text of one finished utterance."""

    @abstractmethod
    async def transcribe_batch(self, audio_data: bytes, sample_rate: int) -> str:
        """Transcribe one complete 16-bit mono PCM buffer (one utterance)."""

    @abstractmethod
    def is_available(self) -> bool:
        """True if the engine is loaded/configured."""
