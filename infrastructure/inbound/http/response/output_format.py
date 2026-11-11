from fastapi import Request

from infrastructure.inbound.http.helpers.media_types import NDJSON, SSE
from infrastructure.inbound.http.response.stream_events import Formatter, ndjson_format, sse_format


def output_format(request: Request) -> tuple[Formatter, str]:
    """How the text events are framed, and the media type: NDJSON when the caller accepts it, else SSE."""
    if NDJSON in request.headers.get("accept", "").lower():
        return ndjson_format, NDJSON
    return sse_format, SSE
