from collections.abc import Awaitable, Callable
from typing import Any

from contracts.stream.codec import EventSequencer
from contracts.stream.common.error import ErrorEvent, ErrorEventDTO
from contracts.stream.common.start_stream import StartStreamEvent
from contracts.stream.common.input_completed import InputCompletedEvent, InputCompletedEventDTO
from fastapi import status
from fastapi.responses import Response
from shared_logging import get_logger
from starlette.types import Receive, Scope, Send

from infrastructure.inbound.http.stream_events import Formatter, sse_format

logger = get_logger(__name__)


class InputStreamResponse(Response):
    """Acknowledges an upload immediately, runs it, then reports how it ended.

    Sends ``stream_started`` as soon as the response starts, awaits ``runner`` (which consumes
    the request body) and finishes with a ``completed`` or ``error`` event. The response has to
    stay open meanwhile: once a response completes the ASGI server stops delivering the body.
    """

    def __init__(
        self,
        runner: Callable[[], Awaitable[Any]],
        *,
        formatter: Formatter = sse_format,
        media_type: str = "text/event-stream",
        status_code: int = status.HTTP_200_OK,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(
            content=b"", status_code=status_code, headers=headers, media_type=media_type
        )
        self.formatter = formatter
        self.runner = runner
        self.raw_headers = [
            (name, value) for name, value in self.raw_headers if name.lower() != b"content-length"
        ]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        events = EventSequencer()
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self.raw_headers,
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": self.formatter(events.next(StartStreamEvent)).encode("utf-8"),
                "more_body": True,
            }
        )
        try:
            await self.runner()
        except Exception as error:
            logger.error("Input stream failed", error=error)
            final = events.next(
                ErrorEvent,
                ErrorEventDTO(code="stream_failed", message=str(error), recoverable=True),
            )
        else:
            final = events.next(InputCompletedEvent, InputCompletedEventDTO())
        await send(
            {
                "type": "http.response.body",
                "body": self.formatter(final).encode("utf-8"),
                "more_body": False,
            }
        )
