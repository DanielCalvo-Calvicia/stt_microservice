"""Decodes an NDJSON request body of STT inbound contract events into audio for the application."""

import base64
from collections.abc import AsyncIterator
from typing import Any

from contracts.stream.codec import NdjsonDecoder
from contracts.stream.common.base import BaseEvent, EventType
from contracts.stream.schemas import STT_INBOUND
from shared_logging import get_logger

from application.dtos.completed_audio_segment import CompletedAudioSegment
from domain.operations.silence import silence_boundary_chunks
from domain.value_objects.stream_settings import StreamSettings

logger = get_logger(__name__)


def _audio_format_hint(audio: bytes) -> str:
    if audio.startswith(b"RIFF"):
        return "wav"
    if audio.startswith(b"OggS"):
        return "ogg"
    if audio.startswith(b"ID3"):
        return "mp3"
    return "pcm_s16le"


def _decode(encoded: str, event: BaseEvent[Any], field: str) -> bytes:
    # ``validate=True``: a corrupt chunk must fail the stream, not be silently mangled into noise.
    try:
        return base64.b64decode(encoded, validate=True)
    except ValueError as error:
        raise ValueError(
            f"{event.type.value} event sequence {event.sequence} payload.{field} is not valid base64"
        ) from error


def _check_format(event: BaseEvent[Any], settings: StreamSettings) -> None:
    """``stream_started`` announces the audio format; it must be the one this stream is set up for."""
    announced = event.payload
    if announced.sample_rate != settings.sample_rate or announced.channels != 1:
        raise ValueError(
            f"stream announces {announced.sample_rate} Hz x {announced.channels} channel(s) but STT "
            f"was set for {settings.sample_rate} Hz mono"
        )


def _audio_items(
    event: BaseEvent[Any], boundary_chunks: list[bytes], settings: StreamSettings
) -> list[bytes | CompletedAudioSegment]:
    """The audio one event contributes: partial chunks, or the end of an utterance."""
    if event.type is EventType.START_STREAM:
        _check_format(event, settings)
        return []
    if event.type is EventType.PARTIAL:
        audio = _decode(event.payload.bytes_base64, event, "bytes_base64")
        logger.info(
            "Decoded STT partial audio event",
            sequence=event.sequence,
            bytes=len(audio),
            format_hint=_audio_format_hint(audio),
        )
        return [audio]
    if event.type is EventType.COMPLETED:
        # A completed event that carries no audio only marks the end of the utterance in progress:
        # it becomes enough silence to make the silence detector close it.
        if not event.payload.output_bytes_base64:
            return list(boundary_chunks)
        audio = _decode(event.payload.output_bytes_base64, event, "output_bytes_base64")
        logger.info(
            "Decoded STT completed audio event",
            sequence=event.sequence,
            bytes=len(audio),
            format_hint=_audio_format_hint(audio),
        )
        return [CompletedAudioSegment(audio_data=audio, source_sequence=event.sequence)]
    if event.type is EventType.ERROR:
        raise RuntimeError(f"{event.payload.code}: {event.payload.message}")
    return []  # heartbeat


async def ndjson_audio_stream(
    source: AsyncIterator[bytes], settings: StreamSettings
) -> AsyncIterator[bytes | CompletedAudioSegment]:
    """Yield the audio of STT inbound events, validating the contract as it goes.

    Raises ``ContractViolation`` (a ``ValueError``) for a malformed event, a wrong sequence number
    or a missing ``stream_started``, and ``RuntimeError`` when the sender reports an ``error``.
    """
    decoder = NdjsonDecoder(STT_INBOUND)
    boundary_chunks = silence_boundary_chunks(settings)
    async for chunk in source:
        if not chunk:
            continue
        for event in decoder.feed(chunk):
            for item in _audio_items(event, boundary_chunks, settings):
                yield item
    for event in decoder.finish():
        for item in _audio_items(event, boundary_chunks, settings):
            yield item
