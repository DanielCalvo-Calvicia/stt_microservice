import asyncio
import logging
import traceback
import httpx
from typing import AsyncIterator

from application.dtos.adapter_inbound_dtos import ProcessStreamRequestDto

logger = logging.getLogger(__name__)


class VoiceStreamAutoloader:
    def __init__(self, stream_url: str, inbound_adapter):
        self.stream_url = stream_url
        self.inbound_adapter = inbound_adapter
        self._task = None
        logger.info("VoiceStreamAutoloader initialized for stream URL %s.", stream_url)

    def start(self):
        if self._task is None or self._task.done():
            logger.info("Creating VoiceStreamAutoloader worker task.")
            self._task = asyncio.create_task(self._worker())
        else:
            logger.info("VoiceStreamAutoloader worker task is already running.")

    async def stop(self):
        if self._task and not self._task.done():
            logger.info("Cancelling VoiceStreamAutoloader worker task.")
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.info("VoiceStreamAutoloader worker task cancelled.")
                pass
            self._task = None
        else:
            logger.info("VoiceStreamAutoloader stop requested with no active task.")

    async def _worker(self):
        method = "POST"
        logger.info("VoiceStreamAutoloader worker loop started.")
        while True:
            try:
                logger.info("Connecting to voice stream at %s via %s.", self.stream_url, method)
                print(f"[Autoloader Worker] Connecting to voice stream at {self.stream_url} via {method}...", flush=True)
                # We use timeout=None to allow an infinitely long stream
                async with httpx.AsyncClient(timeout=None) as client:
                    kwargs = {"json": {}} if method == "POST" else {}
                    async with client.stream(method, self.stream_url, **kwargs) as response:
                        if response.status_code == 405 and method == "POST":
                            logger.warning("Voice stream rejected POST with 405. Falling back to GET.")
                            print(f"[Autoloader Worker] Method {method} not allowed. Falling back to GET...", flush=True)
                            method = "GET"
                            continue
                            
                        response.raise_for_status()
                        logger.info("Connected to voice stream at %s with status %s.", self.stream_url, response.status_code)
                        print(f"[Autoloader Worker] Connected! Streaming from {self.stream_url}", flush=True)
                        
                        async def stream_generator() -> AsyncIterator[bytes]:
                            async for chunk in response.aiter_bytes():
                                logger.debug("Autoloader received stream chunk: bytes=%s.", len(chunk))
                                yield chunk
                                
                        dto = ProcessStreamRequestDto(
                            audio_stream=stream_generator(),
                            sample_rate=16000,
                            chunk_size=1024,
                            silence_threshold=150,
                            silence_limit_seconds=2.0
                        )
                        
                        stt_response = await self.inbound_adapter.process_stream(dto)
                        
                        async for text in stt_response.text_stream:
                            if text:
                                logger.info("Autoload transcription received: text_length=%s.", len(text))
                                print(f"\n[Autoload Transcription] {text}\n", flush=True)
                                
            except httpx.RequestError as e:
                logger.warning("Voice stream connection error: %s. Reconnecting in 5 seconds.", e)
                print(f"[Autoloader Worker] Connection error: {e}. Reconnecting in 5s...", flush=True)
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                logger.info("VoiceStreamAutoloader worker loop cancelled.")
                print("[Autoloader Worker] Cancelled.", flush=True)
                break
            except Exception as e:
                logger.exception("Unexpected VoiceStreamAutoloader error. Reconnecting in 5 seconds.")
                print(f"[Autoloader Worker] Unexpected error: {e}", flush=True)
                traceback.print_exc()
                await asyncio.sleep(5)
