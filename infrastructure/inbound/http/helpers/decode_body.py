from collections.abc import AsyncIterator

from fastapi import Request
from shared_logging import get_logger

from application.errors import UnsupportedInput
from domain.value_objects.audio_utterance import AudioUtterance
from infrastructure.inbound.http.helpers.media_types import NDJSON
from infrastructure.inbound.http.helpers.ndjson_audio_input import ndjson_utterances

logger = get_logger(__name__)


def is_ndjson_request(request: Request) -> bool:
    return NDJSON in request.headers.get("content-type", "").lower()


async def request_body_chunks(request: Request) -> AsyncIterator[bytes]:
    async for chunk in request.stream():
        logger.debug("Received stream chunk", bytes=len(chunk))
        yield chunk


def utterances_of(request: Request) -> AsyncIterator[AudioUtterance]:
    """The utterances in the request body: NDJSON events of the STT inbound contract, nothing else."""
    if not is_ndjson_request(request):
        raise UnsupportedInput(
            "the body must be NDJSON events of the STT inbound contract (Content-Type: application/x-ndjson)"
        )
    return ndjson_utterances(request_body_chunks(request))
