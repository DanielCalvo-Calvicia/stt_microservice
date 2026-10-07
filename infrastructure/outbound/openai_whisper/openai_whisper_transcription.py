"""Outbound adapter: transcription through the OpenAI Whisper API.

Implements ``TranscriptionPort``. Each finished utterance (the microphone cuts them) is sent to
the API as a WAV file.
"""

import asyncio
import os
import tempfile
import wave
from typing import Any

from openai import OpenAI
from shared_logging import get_logger

from application.ports.outbound.transcription_port import TranscriptionPort

logger = get_logger(__name__)

_SAMPLE_WIDTH_BYTES = 2  # 16-bit signed PCM
_WAV_CHANNELS = 1  # always mono
_WHISPER_MODEL = "whisper-1"


def _write_wav_file(raw_pcm: bytes, sample_rate: int) -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_file:
        wav_path = wav_file.name
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(_WAV_CHANNELS)
        wf.setsampwidth(_SAMPLE_WIDTH_BYTES)
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


def _call_whisper_api(client: OpenAI, wav_path: str, language: str, prompt: str = "") -> str:
    logger.info(
        "Calling OpenAI transcription API",
        model=_WHISPER_MODEL,
        language=language,
        prompted=bool(prompt),
    )
    options: dict[str, Any] = {}
    if prompt:
        options["prompt"] = prompt  # words the model should spell the way they are written here
    with open(wav_path, "rb") as audio_file:
        result = client.audio.transcriptions.create(
            model=_WHISPER_MODEL,
            file=audio_file,
            language=language,
            temperature=0.0,
            response_format="text",
            **options,
        )
    return result.strip() if isinstance(result, str) else str(result)


class OpenAIWhisperTranscription(TranscriptionPort):
    def __init__(self, api_key: str, language: str = "en", prompt: str = "") -> None:
        self._api_key = api_key
        self._language = language or "en"
        self._prompt = prompt
        logger.info("OpenAIWhisperTranscription initialized", language=self._language)

    async def transcribe_batch(self, audio_data: bytes, sample_rate: int) -> str:
        client = OpenAI(api_key=self._api_key)
        wav_path = _write_wav_file(audio_data, sample_rate)
        try:
            text = await asyncio.to_thread(
                _call_whisper_api, client, wav_path, self._language, self._prompt
            )
        finally:
            _remove_temp_file(wav_path)
        logger.info("OpenAI batch transcription completed", text_length=len(text))
        return text

    def is_available(self) -> bool:
        return bool(self._api_key)
