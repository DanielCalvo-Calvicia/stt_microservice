from collections.abc import AsyncIterator
from dataclasses import dataclass

from domain.value_objects.audio_utterance import AudioUtterance


@dataclass(slots=True, frozen=True)
class ProcessStreamInboundDTO:
    """Carries a live stream of finished utterances (the microphone already cut them) into the application."""

    utterances: AsyncIterator[AudioUtterance]
