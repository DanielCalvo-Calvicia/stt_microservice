from fastapi import Request, status
from fastapi.responses import Response, StreamingResponse

from application.dtos.inbound.process_stream_inbound import ProcessStreamInboundDTO
from application.ports.inbound.stt_inbound_port import SttInboundPort
from infrastructure.inbound.http.helpers.decode_body import utterances_of
from infrastructure.inbound.http.helpers.media_types import SSE
from infrastructure.inbound.http.response.http_envelope import failure
from infrastructure.inbound.http.response.stream_events import text_event_stream
from infrastructure.inbound.http.response.stream_headers import stream_headers


async def handle_process_stream(request: Request, inbound: SttInboundPort) -> Response:
    """POST /process/stream: NDJSON utterance events in the body, the text back as SSE in the same request."""
    try:
        result = await inbound.process_stream(ProcessStreamInboundDTO(utterances=utterances_of(request)))
    except Exception as error:
        return failure("process_stream", "Failed to process stream", error)
    return StreamingResponse(
        text_event_stream(result.text_stream),
        media_type=SSE,
        status_code=status.HTTP_200_OK,
        headers=stream_headers("process_stream", "success", "Stream processed successfully"),
    )
