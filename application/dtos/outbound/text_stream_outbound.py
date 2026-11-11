from collections.abc import AsyncIterator
from dataclasses import dataclass

from domain.value_objects.utterance import Utterance


@dataclass(slots=True, frozen=True)
class TextStreamOutboundDTO:
    """A live stream of transcribed utterances handed back to an inbound adapter.

    Items are plain text, or an ``Utterance`` when the stream comes from the wake-phrase gate and carries audio.
    """

    text_stream: AsyncIterator[str | Utterance]
