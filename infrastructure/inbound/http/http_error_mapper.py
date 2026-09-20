from fastapi import status

from application.errors import NoActiveStream, StreamSettingsMismatch
from domain.errors import InvalidStreamSettings


def map_error(error: Exception) -> int:
    """Translate an application/domain error into an HTTP status code.

    404  no stream has been set yet (nothing to read)
    422  the request's stream settings are invalid or contradict the active stream
    500  anything else (engine or stream failure)
    """
    if isinstance(error, NoActiveStream):
        return status.HTTP_404_NOT_FOUND
    if isinstance(error, (InvalidStreamSettings, StreamSettingsMismatch)):
        return status.HTTP_422_UNPROCESSABLE_CONTENT
    return status.HTTP_500_INTERNAL_SERVER_ERROR
