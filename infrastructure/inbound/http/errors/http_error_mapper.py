from fastapi import status

from application.errors import NoActiveStream, UnsupportedInput
from domain.errors import InvalidAudioUtterance


def map_error(error: Exception) -> int:
    """Translate an application/domain error into an HTTP status code.

    404  no stream has been set yet (nothing to read)
    415  the body is not NDJSON events of the STT inbound contract
    422  an utterance is invalid (e.g. a non-positive sample rate)
    500  anything else (engine or stream failure)
    """
    if isinstance(error, NoActiveStream):
        return status.HTTP_404_NOT_FOUND
    if isinstance(error, UnsupportedInput):
        return status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    if isinstance(error, InvalidAudioUtterance):
        return status.HTTP_422_UNPROCESSABLE_CONTENT
    return status.HTTP_500_INTERNAL_SERVER_ERROR
