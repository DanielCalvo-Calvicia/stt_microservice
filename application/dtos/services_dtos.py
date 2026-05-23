from dataclasses import dataclass
from typing import AsyncIterator


# ──────────────────────────────────────────────
# STREAM (Real-time)
# ──────────────────────────────────────────────

@dataclass(slots=True, frozen=True)
class ProcessStreamRequestDto:
    """Service-layer request for real-time stream processing."""
    audio_stream: AsyncIterator[bytes]
    sample_rate: int = 16000
    chunk_size: int = 1024
    silence_threshold: int = 150
    silence_limit_seconds: float = 2.0


@dataclass(slots=True, frozen=True)
class ProcessStreamResponseDto:
    """Service-layer response containing a real-time text stream."""
    text_stream: AsyncIterator[str]


# ──────────────────────────────────────────────
# BATCH (Non real-time)
# ──────────────────────────────────────────────

@dataclass(slots=True, frozen=True)
class ProcessBatchRequestDto:
    """Service-layer request to transcribe a complete audio buffer."""
    audio_data: bytes
    sample_rate: int = 16000


@dataclass(slots=True, frozen=True)
class ProcessBatchResponseDto:
    """Service-layer response containing the full transcribed text."""
    text: str


# ──────────────────────────────────────────────
# AVAILABILITY
# ──────────────────────────────────────────────

@dataclass(slots=True, frozen=True)
class STTAvailabilityRequestDto:
    pass


@dataclass(slots=True, frozen=True)
class STTAvailabilityResponseDto:
    is_available: bool
