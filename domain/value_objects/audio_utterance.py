from dataclasses import dataclass

from domain.errors import InvalidAudioUtterance


@dataclass(slots=True, frozen=True)
class AudioUtterance:
    """One finished utterance, cut by the microphone, to transcribe: 16-bit mono PCM at ``sample_rate``."""

    audio: bytes
    sample_rate: int = 16000

    def __post_init__(self) -> None:
        if self.sample_rate <= 0:
            raise InvalidAudioUtterance("sample_rate must be positive")
        if len(self.audio) % 2:
            raise InvalidAudioUtterance("16-bit PCM audio must be a whole number of samples")
