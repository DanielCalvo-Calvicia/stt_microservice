from dataclasses import dataclass
from typing import AsyncIterator, Optional


# ──────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────

@dataclass(slots=True, frozen=True)
class InitInboundAdapterDto:
    autoload_voice_stream_url: Optional[str] = None


# ──────────────────────────────────────────────
# STREAM (Real-time)
# ──────────────────────────────────────────────

@dataclass(slots=True, frozen=True)
class ProcessStreamRequestDto:
    """Inbound request to process a real-time audio stream."""
    audio_stream: AsyncIterator[bytes]
    sample_rate: int = 16000
    chunk_size: int = 1024
    silence_threshold: int = 150
    silence_limit_seconds: float = 2.0


@dataclass(slots=True, frozen=True)
class ProcessStreamResponseDto:
    """Inbound response containing a real-time text stream."""
    text_stream: AsyncIterator[str]


# ──────────────────────────────────────────────
# BATCH (Non real-time)
# ──────────────────────────────────────────────

@dataclass(slots=True, frozen=True)
class ProcessBatchRequestDto:
    """Inbound request to transcribe a complete audio buffer."""
    audio_data: bytes
    sample_rate: int = 16000


@dataclass(slots=True, frozen=True)
class ProcessBatchResponseDto:
    """Inbound response containing the full transcribed text."""
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
