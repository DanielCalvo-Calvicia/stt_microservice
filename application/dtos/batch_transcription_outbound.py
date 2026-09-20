from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class BatchTranscriptionOutboundDTO:
    """The full text transcribed from a batch."""

    text: str
