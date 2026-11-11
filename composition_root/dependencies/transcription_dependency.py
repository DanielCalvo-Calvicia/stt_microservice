from shared_logging import get_logger

from application.errors import EngineNotConfigured
from application.ports.outbound.stt_outbound_port import SttOutboundPort
from infrastructure.config.stt_config import SttConfig

logger = get_logger(__name__)


def new_transcription(cfg: SttConfig) -> SttOutboundPort:
    """Pick the engine: ``openai`` = Whisper API, anything else = local faster-whisper."""
    logger.info("Creating STT engine", engine=cfg.engine, language=cfg.language)
    if cfg.engine == "openai":
        if not cfg.openai_api_key:
            raise EngineNotConfigured("OPENAI_API_KEY is required for OpenAI STT engine")
        from infrastructure.outbound.openai_whisper.openai_whisper_transcription import (
            OpenAIWhisperTranscription,
        )

        return OpenAIWhisperTranscription(api_key=cfg.openai_api_key, language=cfg.language, prompt=cfg.prompt)

    from infrastructure.outbound.local_whisper.local_whisper_transcription import (
        LocalWhisperTranscription,
    )

    return LocalWhisperTranscription(
        language=cfg.language,
        model_name=cfg.model,
        cpu_threads=cfg.threads,
        compute_type=cfg.compute_type,
    )
