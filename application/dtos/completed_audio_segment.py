from dataclasses import dataclass
from typing import Any


@dataclass(slots=True, frozen=True)
class CompletedAudioSegment:
    """A whole utterance that the sender already delimited; it is transcribed as one batch."""

    audio_data: bytes
    source_sequence: Any = None
