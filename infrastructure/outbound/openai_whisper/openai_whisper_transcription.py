"""Outbound adapter: transcription through the OpenAI Whisper API.

Implements ``TranscriptionPort``. A stream is split into utterances by a volume-based
voice-activity detector with an adaptive noise floor; each utterance is sent to the API as WAV.
"""

import asyncio
import os
import tempfile
import wave
from collections.abc import AsyncIterator

import numpy as np
from openai import OpenAI
from shared_logging import get_logger

from application.ports.outbound.transcription_port import TranscriptionPort
from domain.operations.pcm import SAMPLE_WIDTH_BYTES, PcmChunkAligner
from domain.operations.silence import silence_limit_chunks
from domain.value_objects.stream_settings import StreamSettings

logger = get_logger(__name__)

_EMA_DECAY = 0.9
_EMA_ADAPT = 0.1
_WAV_CHANNELS = 1  # always mono
_WHISPER_MODEL = "whisper-1"


def _write_wav_file(raw_pcm: bytes, sample_rate: int) -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_file:
        wav_path = wav_file.name
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(_WAV_CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH_BYTES)
        wf.setframerate(sample_rate)
        wf.writeframes(raw_pcm)
    logger.debug("Temporary WAV file created", wav_path=wav_path)
    return wav_path


def _remove_temp_file(path: str) -> None:
    try:
        os.remove(path)
        logger.debug("Temporary WAV file removed", path=path)
    except OSError:
        logger.warning("Failed to remove temporary WAV file", path=path)


def _call_whisper_api(client: OpenAI, wav_path: str, language: str) -> str:
    logger.info("Calling OpenAI transcription API", model=_WHISPER_MODEL, language=language)
    with open(wav_path, "rb") as audio_file:
        result = client.audio.transcriptions.create(
            model=_WHISPER_MODEL,
            file=audio_file,
            language=language,
            temperature=0.0,
            response_format="text",
        )
    return result.strip() if isinstance(result, str) else str(result)


class _OpenAITextStream(AsyncIterator[str]):
    def __init__(
        self,
        settings: StreamSettings,
        audio_stream: AsyncIterator[bytes],
        client: OpenAI,
        language: str,
    ) -> None:
        self._settings = settings
        self._audio_stream = audio_stream
        self._client = client
        self._language = language
        logger.info("OpenAI text stream initialized", settings=settings, language=language)

        self._audio_buffer = bytearray()
        self._silent_chunks = 0
        self._chunks_seen = 0
        self._bytes_seen = 0
        self._last_volume: int | None = None
        self._aligner = PcmChunkAligner()
        self._silence_limit_chunks = silence_limit_chunks(settings)

        self._smoothed_volume = 0.0
        self._noise_floor = float("inf")
        self._noise_samples = 0
        self._is_speaking = False

    def __aiter__(self) -> "_OpenAITextStream":
        return self

    async def __anext__(self) -> str:
        while True:
            try:
                async for chunk in self._audio_stream:
                    self._chunks_seen += 1
                    self._bytes_seen += len(chunk)
                    pcm_chunk = self._aligner.align(chunk)
                    volume = self._compute_volume(pcm_chunk)
                    self._last_volume = volume
                    self._log_status(volume)

                    if not self._is_speaking and volume >= self._start_threshold():
                        self._is_speaking = True
                        self._silent_chunks = 0
                        logger.info("OpenAI stream detected speech start", volume=volume)

                    if self._is_speaking:
                        self._audio_buffer.extend(pcm_chunk)

                    self._update_silence_counter(volume)

                    if self._is_speaking and self._is_utterance_complete():
                        logger.info(
                            "OpenAI stream detected utterance end",
                            buffered_bytes=len(self._audio_buffer),
                        )
                        text = await self._transcribe_utterance()
                        if text:
                            return text
                        continue
            except Exception:
                logger.exception(
                    "OpenAI audio stream failed reading upstream audio",
                    chunks_seen=self._chunks_seen,
                    bytes_seen=self._bytes_seen,
                    buffered_bytes=len(self._audio_buffer),
                    is_speaking=self._is_speaking,
                    silent_chunks=self._silent_chunks,
                    silence_limit_chunks=self._silence_limit_chunks,
                )
                raise

            logger.info(
                "OpenAI audio stream exhausted",
                chunks_seen=self._chunks_seen,
                bytes_seen=self._bytes_seen,
                buffered_bytes=len(self._audio_buffer),
                is_speaking=self._is_speaking,
                silent_chunks=self._silent_chunks,
                silence_limit_chunks=self._silence_limit_chunks,
                last_volume=self._last_volume,
                start_threshold=self._start_threshold(),
                effective_threshold=self._effective_threshold(),
            )
            if self._is_speaking and len(self._audio_buffer) > 0:
                if self._aligner.drop_pending():
                    logger.warning(
                        "OpenAI audio stream ended with one incomplete PCM byte; dropping it",
                    )
                logger.info(
                    "OpenAI audio stream ended mid-utterance; transcribing the final buffer",
                    buffered_bytes=len(self._audio_buffer),
                )
                text = await self._transcribe_utterance()
                if text:
                    return text
            raise StopAsyncIteration

    def _compute_volume(self, chunk: bytes) -> int:
        if len(chunk) == 0:
            return 0
        data = np.frombuffer(chunk, dtype=np.int16)
        raw_volume = (
            0 if len(data) == 0 else int(np.sqrt(np.mean(np.square(data.astype(np.float64)))))
        )
        self._track_noise_floor(raw_volume)
        return self._smooth_volume(raw_volume)

    def _track_noise_floor(self, raw_volume: float) -> None:
        if raw_volume == 0:
            return
        if raw_volume < self._noise_floor:
            self._noise_floor = raw_volume
        if self._noise_samples < 100:
            self._noise_samples += 1

    def _smooth_volume(self, raw_volume: float) -> int:
        self._smoothed_volume = self._smoothed_volume * _EMA_DECAY + raw_volume * _EMA_ADAPT
        return int(self._smoothed_volume)

    def _log_status(self, volume: int) -> None:
        logger.debug(
            "OpenAI stream status",
            volume=volume,
            start_threshold=self._start_threshold(),
            effective_threshold=self._effective_threshold(),
            silent_chunks=self._silent_chunks,
            speaking=self._is_speaking,
        )

    def _update_silence_counter(self, volume: int) -> None:
        if self._is_speaking and volume < self._effective_threshold():
            self._silent_chunks += 1
        else:
            self._silent_chunks = 0

    def _effective_threshold(self) -> int:
        if self._noise_floor == float("inf"):
            return self._settings.silence_threshold
        return max(self._settings.silence_threshold, int(self._noise_floor * 2.0))

    def _start_threshold(self) -> int:
        if self._noise_floor == float("inf"):
            return self._settings.silence_threshold * 2
        return max(self._settings.silence_threshold * 2, int(self._noise_floor * 3.0))

    def _is_utterance_complete(self) -> bool:
        return self._silent_chunks >= self._silence_limit_chunks

    async def _transcribe_utterance(self) -> str:
        if len(self._audio_buffer) == 0:
            self._silent_chunks = 0
            return ""

        logger.info(
            "Sending utterance to OpenAI Whisper",
            bytes=len(self._audio_buffer),
            sample_rate=self._settings.sample_rate,
        )
        text = await asyncio.to_thread(
            self._transcribe_with_openai, bytes(self._audio_buffer), self._settings.sample_rate
        )
        self._reset_buffers()

        logger.info("OpenAI Whisper returned", text_length=len(text))
        return text

    def _reset_buffers(self) -> None:
        self._audio_buffer.clear()
        self._silent_chunks = 0
        self._is_speaking = False

    def _transcribe_with_openai(self, raw_pcm: bytes, sample_rate: int) -> str:
        wav_path = _write_wav_file(raw_pcm, sample_rate)
        try:
            return _call_whisper_api(self._client, wav_path, self._language)
        finally:
            _remove_temp_file(wav_path)


class OpenAIWhisperTranscription(TranscriptionPort):
    def __init__(self, api_key: str, language: str = "en") -> None:
        self._api_key = api_key
        self._language = language or "en"
        logger.info("OpenAIWhisperTranscription initialized", language=self._language)

    async def transcribe_stream(
        self, settings: StreamSettings, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[str]:
        return _OpenAITextStream(
            settings, audio_stream, OpenAI(api_key=self._api_key), self._language
        )

    async def transcribe_batch(self, audio_data: bytes, sample_rate: int) -> str:
        client = OpenAI(api_key=self._api_key)
        wav_path = _write_wav_file(audio_data, sample_rate)
        try:
            text = await asyncio.to_thread(_call_whisper_api, client, wav_path, self._language)
        finally:
            _remove_temp_file(wav_path)
        logger.info("OpenAI batch transcription completed", text_length=len(text))
        return text

    def is_available(self) -> bool:
        return bool(self._api_key)
