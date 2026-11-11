from contracts.api.microservices.common.health_check import HealthCheckResponse
from fastapi.responses import JSONResponse

from application.ports.inbound.stt_inbound_port import SttInboundPort
from infrastructure.inbound.http.response.http_envelope import success


async def handle_health(inbound: SttInboundPort) -> JSONResponse:
    """GET /health: liveness. 200 while the process answers HTTP."""
    return success("health_check", "Service is healthy", HealthCheckResponse(healthy=inbound.health()))
