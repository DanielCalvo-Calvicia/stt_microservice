from contracts.api.microservices.common.availability import AvailabilityResponse
from fastapi.responses import JSONResponse

from application.ports.inbound.stt_inbound_port import SttInboundPort
from infrastructure.inbound.http.response.http_envelope import failure, success


async def handle_available(inbound: SttInboundPort) -> JSONResponse:
    """GET /available: true when the engine (and the gate, when it runs) is ready. No network call."""
    try:
        available = inbound.is_available()
    except Exception as error:
        return failure("check_availability", "Failed to check availability", error)
    return success(
        "check_availability",
        "Availability checked successfully",
        AvailabilityResponse(is_available=available),
    )
