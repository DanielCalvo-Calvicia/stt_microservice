from fastapi import FastAPI
from shared_logging import TracingMiddleware, get_logger

from application.errors import EngineNotConfigured
from application.ports.inbound.stt_transcription_port import SttTranscriptionPort
from application.ports.outbound.transcription_port import TranscriptionPort, UtteranceTranscriptionPort
from application.services.stt_service import SttService
from infrastructure.config.stt_config import SttConfig
from infrastructure.inbound.http.http_handler import GATE_PREFIX, SttHandler

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


def new_gate_transcription(cfg: SttConfig) -> UtteranceTranscriptionPort:
    """The wake-phrase gate's engine: a small local model, free to run on every utterance, that returns the audio too.

    ``beam_size=1`` (greedy decoding) keeps it fast; ``gate_prompt`` biases the model toward the phrase it listens for.
    """
    logger.info("Creating the wake-phrase gate engine", model=cfg.gate_model, prompt=cfg.gate_prompt)
    from infrastructure.outbound.local_whisper.local_whisper_transcription import (
        LocalWhisperTranscription,
    )

    return LocalWhisperTranscription(
        language=cfg.language, model_name=cfg.gate_model, initial_prompt=cfg.gate_prompt or None, beam_size=1
    )


def new_stt_service(transcription: TranscriptionPort, name: str, *, with_audio: bool = False) -> SttTranscriptionPort:
    return SttService(transcription=transcription, name=name, with_audio=with_audio)


def new_http_app(port: SttTranscriptionPort, name: str, gate_port: SttTranscriptionPort | None = None) -> FastAPI:
    app = FastAPI(
        title=name,
        description=f"HTTP adapter exposing {name}",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.include_router(SttHandler(port, gate=gate_port).router)
    if gate_port is not None:
        app.include_router(SttHandler(gate_port, prefix=GATE_PREFIX, include_audio=True).router)
    app.add_middleware(TracingMiddleware)
    return app
