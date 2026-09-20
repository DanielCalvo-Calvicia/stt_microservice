from collections.abc import AsyncIterator
from dataclasses import dataclass

from application.dtos.completed_audio_segment import CompletedAudioSegment


@dataclass(slots=True, frozen=True)
class SetStreamInboundDTO:
    """Feeds the shared stream; the audio may contain already-delimited utterances."""

    audio_stream: AsyncIterator[bytes | CompletedAudioSegment]
    sample_rate: int = 16000
    chunk_size: int = 1024
    silence_threshold: int = 150
    silence_limit_seconds: float = 2.0
