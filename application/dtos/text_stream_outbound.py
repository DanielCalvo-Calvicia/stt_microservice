from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class TextStreamOutboundDTO:
    """A live stream of transcribed utterances handed back to an inbound adapter."""

    text_stream: AsyncIterator[str]
