"""Outbound adapter: local transcription with faster-whisper on the CPU.

Implements ``TranscriptionPort``. Each finished utterance (the microphone cuts them) is
transcribed in a worker thread.
"""

import asyncio
from typing import Any

import numpy as np
from faster_whisper import WhisperModel
from shared_logging import get_logger

from application.ports.outbound.transcription_port import TranscriptionPort

logger = get_logger(__name__)

DEFAULT_MODEL_NAME = "small.en"
_WHISPER_SAMPLE_RATE = 16000


def _pcm_to_whisper_input(audio_data: bytes, sample_rate: int) -> "np.ndarray[Any, Any]":
    """16-bit PCM bytes -> float32 samples in [-1, 1] at Whisper's 16 kHz."""
    samples = np.frombuffer(audio_data, np.int16).flatten().astype(np.float32) / 32768.0
    if sample_rate != _WHISPER_SAMPLE_RATE:
        logger.info(
            "Resampling audio to the Whisper sample rate",
            sample_rate=sample_rate,
            whisper_sample_rate=_WHISPER_SAMPLE_RATE,
        )
        target_len = int(len(samples) * _WHISPER_SAMPLE_RATE / sample_rate)
        original_indices = np.arange(len(samples))
        target_indices = np.linspace(0, len(samples) - 1, target_len)
        samples = np.interp(target_indices, original_indices, samples).astype(np.float32)
    return samples


class LocalWhisperTranscription(TranscriptionPort):
    def __init__(
        self,
        language: str = "en",
        model_name: str = DEFAULT_MODEL_NAME,
        *,
        initial_prompt: str | None = None,
        beam_size: int = 5,
    ) -> None:
        self._language = language or "en"
        self._initial_prompt = initial_prompt
        self._beam_size = beam_size
        logger.info(
            "Loading local Whisper model on CPU with int8 compute",
            model_name=model_name,
        )
        self._model = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=2)
        logger.info(
            "Local Whisper model loaded",
            model_name=model_name,
            language=self._language,
        )

    async def transcribe_batch(self, audio_data: bytes, sample_rate: int) -> str:
        return await asyncio.to_thread(self._transcribe_sync, audio_data, sample_rate)

    def _transcribe_sync(self, audio_data: bytes, sample_rate: int) -> str:
        samples = _pcm_to_whisper_input(audio_data, sample_rate)
        options: dict[str, Any] = {
            "beam_size": self._beam_size,
            "language": self._language,
            "condition_on_previous_text": False,
            "no_speech_threshold": 0.65,
        }
        if self._initial_prompt:
            options["initial_prompt"] = self._initial_prompt  # biases the model toward these words
        segments, _info = self._model.transcribe(samples, **options)
        return "".join(s.text for s in segments if s.text.strip())

    def is_available(self) -> bool:
        return self._model is not None
