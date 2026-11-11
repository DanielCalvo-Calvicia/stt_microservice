from fastapi import Request, status
from fastapi.responses import Response
from shared_logging import get_logger

from application.dtos.inbound.set_stream_inbound import SetStreamInboundDTO
from application.ports.inbound.stt_inbound_port import SttInboundPort
from infrastructure.inbound.http.helpers.decode_body import utterances_of
from infrastructure.inbound.http.response.http_envelope import failure
from infrastructure.inbound.http.response.input_stream_response import InputStreamResponse
from infrastructure.inbound.http.response.output_format import output_format
from infrastructure.inbound.http.response.stream_headers import stream_headers

logger = get_logger(__name__)


async def handle_set_stream(request: Request, inbound: SttInboundPort) -> Response:
    """POST /process/stream/set: feed the shared stream with NDJSON utterance events; the answer is the ack stream."""
    try:
        dto = SetStreamInboundDTO(utterances=utterances_of(request))
    except Exception as error:
        return failure("set_stream", "Failed to set stream", error)

    async def run_set_stream() -> None:
        await inbound.set_stream(dto)
        logger.info("Set stream completed")

    formatter, media_type = output_format(request)
    return InputStreamResponse(
        run_set_stream,
        formatter=formatter,
        media_type=media_type,
        status_code=status.HTTP_200_OK,
        headers=stream_headers("set_stream", "accepted", "Input stream connection established"),
    )
