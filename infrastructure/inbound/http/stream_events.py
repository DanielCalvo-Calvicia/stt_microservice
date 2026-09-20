"""Frames transcribed text as the STT outbound stream contract (SSE or NDJSON events)."""

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import suppress
from typing import Any

from contracts.stream.codec import EventSequencer, encode_ndjson, encode_sse
from contracts.stream.common.base import BaseEvent
from contracts.stream.common.error import ErrorEvent, ErrorEventDTO
from contracts.stream.common.heartbeat import HeartbeatEvent
from contracts.stream.common.start_stream import StartStreamEvent
from contracts.stream.microservices.stt.outbound.completed import (
    STTCompletedOutboundEvent,
    STTCompletedOutboundEventDTO,
)
from contracts.stream.microservices.stt.outbound.partial import (
    STTPartialOutboundEvent,
    STTPartialOutboundEventDTO,
)
from shared_logging import get_logger

logger = get_logger(__name__)

# How one event is put on the wire: the same events, either as Server-Sent Events or as NDJSON.
Formatter = Callable[[BaseEvent[Any]], str]


def sse_format(event: BaseEvent[Any]) -> str:
    return encode_sse(event)


def ndjson_format(event: BaseEvent[Any]) -> str:
    return encode_ndjson(event).decode("utf-8")


async def text_event_stream(
    text_stream: AsyncIterator[str],
    *,
    completion_reason: str = "completed",
    formatter: Formatter = sse_format,
    emit_empty_completion_on_end: bool = True,
    heartbeat_interval_seconds: float | None = None,
) -> AsyncIterator[str]:
    """``stream_started``, then per transcribed utterance a ``partial`` and a ``completed``.

    ``partial`` and ``completed`` carry the same text: the transcription engine only produces
    finished utterances, so there is no interim hypothesis to send. When nothing arrives for
    ``heartbeat_interval_seconds`` a ``heartbeat`` keeps the connection alive.
    """
    events = EventSequencer()
    emitted_text = False
    yield formatter(events.next(StartStreamEvent))

    iterator = text_stream.__aiter__()
    pending_text: asyncio.Future[str] | None = None
    try:
        pending_text = asyncio.ensure_future(iterator.__anext__())
        while True:
            done, _pending = await asyncio.wait(
                {pending_text},
                timeout=heartbeat_interval_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                body = formatter(events.next(HeartbeatEvent))
                logger.info("Emitting STT stream heartbeat", bytes=len(body.encode("utf-8")))
                yield body
                continue
            try:
                text = pending_text.result()
            except StopAsyncIteration:
                break
            if not text:
                pending_text = asyncio.ensure_future(iterator.__anext__())
                continue
            emitted_text = True
            yield formatter(events.next(STTPartialOutboundEvent, STTPartialOutboundEventDTO(text=text)))
            yield formatter(
                events.next(
                    STTCompletedOutboundEvent,
                    STTCompletedOutboundEventDTO(reason=completion_reason, output=text),
                )
            )
            pending_text = asyncio.ensure_future(iterator.__anext__())
        if emit_empty_completion_on_end and not emitted_text:
            yield formatter(
                events.next(
                    STTCompletedOutboundEvent,
                    STTCompletedOutboundEventDTO(reason=completion_reason, output=""),
                )
            )
    except Exception as exc:
        yield formatter(
            events.next(
                ErrorEvent,
                ErrorEventDTO(code="stream_failed", message=str(exc), recoverable=True),
            )
        )
    finally:
        if pending_text is not None and not pending_text.done():
            pending_text.cancel()
            with suppress(asyncio.CancelledError):
                await pending_text
