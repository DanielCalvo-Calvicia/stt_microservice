"""Decodes an NDJSON request body of STT inbound contract events into utterances for the application."""

import base64
from collections.abc import AsyncIterator
from typing import Any

from contracts.stream.codec import NdjsonDecoder
from contracts.stream.common.base import BaseEvent, EventType
from contracts.stream.schemas import STT_INBOUND
from shared_logging import get_logger

from domain.value_objects.audio_utterance import AudioUtterance

logger = get_logger(__name__)

_DEFAULT_SAMPLE_RATE = 16000


def _decode(encoded: str, event: BaseEvent[Any], field: str) -> bytes:
    # ``validate=True``: corrupt audio must fail the stream, not be silently mangled into noise.
    try:
        return base64.b64decode(encoded, validate=True)
    except ValueError as error:
        raise ValueError(
            f"{event.type.value} event sequence {event.sequence} payload.{field} is not valid base64"
        ) from error


class _Utterances:
    """Turns the events of one upload into utterances; remembers the rate ``stream_started`` announced."""

    def __init__(self) -> None:
        self._announced_rate = _DEFAULT_SAMPLE_RATE

    def of(self, event: BaseEvent[Any]) -> list[AudioUtterance]:
        if event.type is EventType.START_STREAM:
            if event.payload.channels != 1:
                raise ValueError(f"stream announces {event.payload.channels} channels but STT takes mono")
            self._announced_rate = event.payload.sample_rate
            return []
        if event.type is EventType.UTTERANCE:
            audio = _decode(event.payload.bytes_base64, event, "bytes_base64")
            logger.info(
                "Decoded STT utterance event",
                sequence=event.sequence,
                bytes=len(audio),
                sample_rate=event.payload.sample_rate,
            )
            return [AudioUtterance(audio, event.payload.sample_rate)]
        if event.type is EventType.COMPLETED:
            # A completed event that carries audio is one more whole utterance, at the announced rate
            if not event.payload.output_bytes_base64:
                return []
            audio = _decode(event.payload.output_bytes_base64, event, "output_bytes_base64")
            logger.info("Decoded STT completed audio event", sequence=event.sequence, bytes=len(audio))
            return [AudioUtterance(audio, self._announced_rate)]
        if event.type is EventType.ERROR:
            raise RuntimeError(f"{event.payload.code}: {event.payload.message}")
        return []  # heartbeat


async def ndjson_utterances(source: AsyncIterator[bytes]) -> AsyncIterator[AudioUtterance]:
    """Yield the utterances of STT inbound events, validating the contract as it goes.

    Raises ``ContractViolation`` (a ``ValueError``) for a malformed event, a wrong sequence number
    or a missing ``stream_started``, and ``RuntimeError`` when the sender reports an ``error``.
    """
    decoder = NdjsonDecoder(STT_INBOUND)
    utterances = _Utterances()
    async for chunk in source:
        if not chunk:
            continue
        for event in decoder.feed(chunk):
            for utterance in utterances.of(event):
                yield utterance
    for event in decoder.finish():
        for utterance in utterances.of(event):
            yield utterance
