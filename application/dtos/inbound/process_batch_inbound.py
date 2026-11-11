from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ProcessBatchInboundDTO:
    """A complete audio buffer to transcribe in one go."""

    audio_data: bytes
    sample_rate: int = 16000
