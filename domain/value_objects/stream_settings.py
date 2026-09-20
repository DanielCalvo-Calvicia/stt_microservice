from dataclasses import dataclass

from domain.errors import InvalidStreamSettings


@dataclass(slots=True, frozen=True)
class StreamSettings:
    """How a PCM (16-bit mono) stream is cut into chunks and split into utterances.

    Invariants: ``sample_rate`` and ``chunk_size`` are strictly positive (silence is measured
    in chunks, so both are divisors); ``silence_threshold`` and ``silence_limit_seconds``
    are not negative.
    """

    sample_rate: int = 16000
    chunk_size: int = 1024
    silence_threshold: int = 150
    silence_limit_seconds: float = 2.0

    def __post_init__(self) -> None:
        if self.sample_rate <= 0 or self.chunk_size <= 0:
            raise InvalidStreamSettings("sample_rate and chunk_size must be positive")
        if self.silence_threshold < 0 or self.silence_limit_seconds < 0:
            raise InvalidStreamSettings(
                "silence_threshold and silence_limit_seconds must not be negative"
            )
