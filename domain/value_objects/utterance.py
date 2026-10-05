from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Utterance:
    """One transcribed utterance: its text and, for the wake-phrase gate, the audio it was transcribed from."""

    text: str
    audio: bytes = b""  # 16-bit mono PCM at the sample rate of the input stream; empty when not kept
