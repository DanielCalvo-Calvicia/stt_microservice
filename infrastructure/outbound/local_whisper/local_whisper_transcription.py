"""Outbound adapter: local transcription with faster-whisper on the CPU.

Implements ``TranscriptionPort``. A stream is split into utterances by a background
volume-based voice-activity task; each utterance is then transcribed in a worker thread.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import numpy as np
from faster_whisper import WhisperModel
from shared_logging import get_logger

from application.ports.outbound.transcription_port import TranscriptionPort
from domain.operations.pcm import PcmChunkAligner
from domain.operations.silence import silence_limit_chunks
from domain.value_objects.stream_settings import StreamSettings

logger = get_logger(__name__)

DEFAULT_MODEL_NAME = "small.en"
_WHISPER_SAMPLE_RATE = 16000
_DC_OFFSET_DECAY = 0.95
_DC_OFFSET_ADAPT = 0.05
_VOLUME_DECAY = 0.9
_VOLUME_ADAPT = 0.1


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


class _LocalTextStream(AsyncIterator[str]):
    def __init__(
        self,
        settings: StreamSettings,
        audio_stream: AsyncIterator[bytes],
        model: Any,  # noqa: ANN401 - faster_whisper is untyped
        language: str,
    ) -> None:
        self._settings = settings
        self._audio_stream = audio_stream
        self._model = model
        self._language = language
        logger.info("Local text stream initialized", settings=settings, language=language)

        self._audio_buffer = bytearray()
        self._silent_chunks = 0
        self._aligner = PcmChunkAligner()
        self._silence_limit_chunks = silence_limit_chunks(settings)

        self._transcription_queue: asyncio.Queue[bytearray | None] = asyncio.Queue()
        self._vad_task = asyncio.create_task(self._continuous_vad())

    def __aiter__(self) -> "_LocalTextStream":
        return self

    async def __anext__(self) -> str:
        while True:
            utterance = await self._transcription_queue.get()
            if utterance is None:
                logger.info("Local text stream received completion sentinel")
                raise StopAsyncIteration

            logger.info("Transcribing utterance locally", bytes=len(utterance))
            text = await asyncio.to_thread(self._transcribe_sync, utterance)
            self._transcription_queue.task_done()

            if text.strip():
                logger.info("Local transcription", text_length=len(text.strip()))
                return text.strip()
            logger.info("Local text stream discarded empty transcription")

    async def _continuous_vad(self) -> None:
        smoothed_volume = 0.0
        dc_offset = 0.0
        threshold = self._settings.silence_threshold
        try:
            async for raw_chunk in self._audio_stream:
                chunk = self._aligner.align(raw_chunk)
                audio_array = np.frombuffer(chunk, dtype=np.int16)
                if len(audio_array) > 0:
                    audio_float = audio_array.astype(np.float32)

                    chunk_mean = float(np.mean(audio_float))
                    dc_offset = (dc_offset * _DC_OFFSET_DECAY) + (chunk_mean * _DC_OFFSET_ADAPT)
                    audio_float -= dc_offset

                    raw_volume = float(np.sqrt(np.mean(np.square(audio_float))))
                    smoothed_volume = (smoothed_volume * _VOLUME_DECAY) + (
                        raw_volume * _VOLUME_ADAPT
                    )
                    volume = int(smoothed_volume)
                else:
                    volume = 0

                logger.debug(
                    "Local VAD",
                    volume=volume,
                    threshold=threshold,
                    silent_chunks=self._silent_chunks,
                )

                if volume < threshold:
                    self._silent_chunks += 1
                else:
                    self._silent_chunks = 0

                if volume >= threshold or len(self._audio_buffer) > 0:
                    self._audio_buffer.extend(chunk)

                if self._silent_chunks >= self._silence_limit_chunks:
                    if len(self._audio_buffer) > 0:
                        logger.info(
                            "Local VAD queued utterance",
                            buffered_bytes=len(self._audio_buffer),
                        )
                        await self._transcription_queue.put(bytearray(self._audio_buffer))
                        self._audio_buffer.clear()
                    self._silent_chunks = 0
        finally:
            if self._aligner.drop_pending():
                logger.warning("Local VAD dropped one trailing incomplete PCM byte")
            if len(self._audio_buffer) > 0:
                logger.info(
                    "Local VAD queued final utterance after audio ended",
                    buffered_bytes=len(self._audio_buffer),
                )
                await self._transcription_queue.put(bytearray(self._audio_buffer))
                self._audio_buffer.clear()
            logger.info("Local continuous VAD loop completed")
            await self._transcription_queue.put(None)

    def _transcribe_sync(self, audio_buffer: bytearray) -> str:
        audio_data = _pcm_to_whisper_input(bytes(audio_buffer), self._settings.sample_rate)
        segments, _info = self._model.transcribe(
            audio_data,
            beam_size=5,
            language=self._language,
            condition_on_previous_text=False,
            no_speech_threshold=0.65,
        )
        text_output = ""
        for segment in segments:
            if segment.text.strip():
                text_output += segment.text
        return text_output


class LocalWhisperTranscription(TranscriptionPort):
    def __init__(self, language: str = "en", model_name: str = DEFAULT_MODEL_NAME) -> None:
        self._language = language or "en"
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

    async def transcribe_stream(
        self, settings: StreamSettings, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[str]:
        return _LocalTextStream(settings, audio_stream, self._model, self._language)

    async def transcribe_batch(self, audio_data: bytes, sample_rate: int) -> str:
        samples = _pcm_to_whisper_input(audio_data, sample_rate)
        segments, _info = await asyncio.to_thread(
            self._model.transcribe,
            samples,
            beam_size=5,
            language=self._language,
            condition_on_previous_text=False,
            no_speech_threshold=0.65,
        )
        return "".join(s.text for s in segments if s.text.strip())

    def is_available(self) -> bool:
        return self._model is not None
