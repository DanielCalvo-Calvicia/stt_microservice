from fastapi import FastAPI
from shared_logging import TracingMiddleware

from application.ports.service.stt_service_port import SttServicePort
from infrastructure.inbound.http.http_handler import GATE_PREFIX, SttHandler


def new_http_app(service: SttServicePort, name: str, gate_service: SttServicePort | None = None) -> FastAPI:
    app = FastAPI(
        title=name,
        description=f"HTTP adapter exposing {name}",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.include_router(SttHandler(service, gate=gate_service).router)
    if gate_service is not None:
        app.include_router(SttHandler(gate_service, prefix=GATE_PREFIX, include_audio=True).router)
    app.add_middleware(TracingMiddleware)
    return app
