from collections.abc import AsyncIterator
from dataclasses import dataclass

from domain.value_objects.audio_utterance import AudioUtterance


@dataclass(slots=True, frozen=True)
class SetStreamInboundDTO:
    """Feeds the shared stream with finished utterances, each transcribed as one batch."""

    utterances: AsyncIterator[AudioUtterance]
