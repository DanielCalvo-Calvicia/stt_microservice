from fastapi import Request, status
from fastapi.responses import Response, StreamingResponse
from shared_logging import get_logger

from application.errors import NoActiveStream
from application.ports.inbound.stt_inbound_port import SttInboundPort
from infrastructure.inbound.http.response.http_envelope import failure, failure_message
from infrastructure.inbound.http.response.output_format import output_format
from infrastructure.inbound.http.response.stream_events import text_event_stream
from infrastructure.inbound.http.response.stream_headers import stream_headers

logger = get_logger(__name__)

HEARTBEAT_SECONDS = 15.0


async def handle_get_stream(request: Request, inbound: SttInboundPort, include_audio: bool) -> Response:
    """GET /process/stream/get: read the transcripts of the stream set with ``/process/stream/set``.

    404 when nothing was set. ``include_audio`` is on for the wake-phrase gate, whose ``completed`` events carry the audio.
    """
    try:
        result = await inbound.get_stream()
    except NoActiveStream as error:
        logger.warning("Get stream rejected", error=error)
        return failure_message("get_stream", str(error), status.HTTP_404_NOT_FOUND, str(error))
    except Exception as error:
        return failure("get_stream", "Failed to get stream", error)

    formatter, media_type = output_format(request)
    return StreamingResponse(
        text_event_stream(
            result.text_stream,
            formatter=formatter,
            emit_empty_completion_on_end=False,
            heartbeat_interval_seconds=HEARTBEAT_SECONDS,
            include_audio=include_audio,
        ),
        media_type=media_type,
        status_code=status.HTTP_200_OK,
        headers=stream_headers("get_stream", "success", "Stream retrieved successfully"),
    )
