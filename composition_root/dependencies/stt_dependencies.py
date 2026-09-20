from fastapi import FastAPI
from shared_logging import TracingMiddleware, get_logger

from application.errors import EngineNotConfigured
from application.ports.inbound.stt_transcription_port import SttTranscriptionPort
from application.ports.outbound.transcription_port import TranscriptionPort
from application.services.stt_service import SttService
from infrastructure.config.stt_config import SttConfig
from infrastructure.inbound.http.http_handler import SttHandler

logger = get_logger(__name__)


def new_transcription(cfg: SttConfig) -> TranscriptionPort:
    """Pick the engine: ``openai`` = Whisper API, anything else = local faster-whisper."""
    logger.info("Creating STT engine", engine=cfg.engine, language=cfg.language)
    if cfg.engine == "openai":
        if not cfg.openai_api_key:
            raise EngineNotConfigured("OPENAI_API_KEY is required for OpenAI STT engine")
        from infrastructure.outbound.openai_whisper.openai_whisper_transcription import (
            OpenAIWhisperTranscription,
        )

        return OpenAIWhisperTranscription(api_key=cfg.openai_api_key, language=cfg.language)

    from infrastructure.outbound.local_whisper.local_whisper_transcription import (
        LocalWhisperTranscription,
    )

    return LocalWhisperTranscription(language=cfg.language)


def new_stt_service(transcription: TranscriptionPort, name: str) -> SttTranscriptionPort:
    return SttService(transcription=transcription, name=name)


def new_http_app(port: SttTranscriptionPort, name: str) -> FastAPI:
    app = FastAPI(
        title=name,
        description=f"HTTP adapter exposing {name}",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.include_router(SttHandler(port).router)
    app.add_middleware(TracingMiddleware)
    return app
