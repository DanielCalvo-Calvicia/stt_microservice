from typing import Any

from contracts.api.common.envelope import ApiEnvelope
from fastapi import status
from fastapi.responses import JSONResponse
from shared_logging import get_logger

from infrastructure.inbound.http.http_error_mapper import map_error

logger = get_logger(__name__)

# The JSON shape of every non-stream answer is the project contract ``ApiEnvelope``; ``data`` is
# the endpoint's contract dataclass (``contracts.api.microservices``).


def success(
    action: str,
    message: str,
    data: Any = None,  # noqa: ANN401 - a contract dataclass or plain JSON
    *,
    code: int = status.HTTP_200_OK,
    state: str = "success",
) -> JSONResponse:
    make = ApiEnvelope.accepted if state == "accepted" else ApiEnvelope.success
    return JSONResponse(
        status_code=code, content=make(action, message, data, status_code=code).to_dict()
    )


def failure(action: str, message: str, error: Exception) -> JSONResponse:
    logger.error("Operation failed", action=action, error=error)
    return failure_message(action, f"{message}: {error}", map_error(error), str(error))


def failure_message(
    action: str,
    message: str,
    code: int,
    data: Any = None,  # noqa: ANN401 - error detail
) -> JSONResponse:
    return JSONResponse(
        status_code=code, content=ApiEnvelope.failure(action, message, code, data).to_dict()
    )
