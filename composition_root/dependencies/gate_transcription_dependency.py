from shared_logging import get_logger

from application.ports.outbound.stt_outbound_port import SttOutboundPort
from infrastructure.config.stt_config import SttConfig

logger = get_logger(__name__)


def new_gate_transcription(cfg: SttConfig) -> SttOutboundPort:
    """The wake-phrase gate's engine: a small local model, free to run on every utterance.

    ``beam_size=1`` (greedy decoding) keeps it fast; ``gate_prompt`` biases the model toward the phrase it listens for.
    The threads and the compute type are the same settings as the main model's.
    """
    logger.info("Creating the wake-phrase gate engine", model=cfg.gate_model, prompt=cfg.gate_prompt)
    from infrastructure.outbound.local_whisper.local_whisper_transcription import (
        LocalWhisperTranscription,
    )

    return LocalWhisperTranscription(
        language=cfg.language,
        model_name=cfg.gate_model,
        initial_prompt=cfg.gate_prompt or None,
        beam_size=1,
        cpu_threads=cfg.threads,
        compute_type=cfg.compute_type,
    )
