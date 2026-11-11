from fastapi.responses import JSONResponse

from application.ports.inbound.stt_inbound_port import SttInboundPort
from infrastructure.inbound.http.response.http_envelope import failure, success


async def handle_stop(inbound: SttInboundPort) -> JSONResponse:
    """POST /stop: stop the shared stream. Does nothing if none is active."""
    try:
        await inbound.stop()
    except Exception as error:
        return failure("stop_stream", "Failed to stop stream", error)
    return success("stop_stream", "Stream stopped successfully")
