import asyncio
from collections.abc import AsyncIterator

from shared_logging import get_logger

from application.dtos.batch_transcription_outbound import BatchTranscriptionOutboundDTO
from application.dtos.completed_audio_segment import CompletedAudioSegment
from application.dtos.process_batch_inbound import ProcessBatchInboundDTO
from application.dtos.process_stream_inbound import ProcessStreamInboundDTO
from application.dtos.set_stream_inbound import SetStreamInboundDTO
from application.dtos.text_stream_outbound import TextStreamOutboundDTO
from application.errors import NoActiveStream, SharedStreamForwardingError
from application.ports.inbound.stt_transcription_port import SttTranscriptionPort
from application.ports.outbound.transcription_port import TranscriptionPort
from domain.value_objects.stream_settings import StreamSettings

logger = get_logger(__name__)

_TextQueue = asyncio.Queue[str | Exception | None]


class SttService(SttTranscriptionPort):
    """Orchestrates the speech-to-text use cases. Business rules live in the domain."""

    def __init__(self, transcription: TranscriptionPort, name: str = "stt_service") -> None:
        self.name = name
        self._transcription = transcription
        self._text_queue: _TextQueue | None = None
        self._settings: StreamSettings | None = None
        self._stream_task: asyncio.Task[None] | None = None
        logger.info(
            "SttService initialized",
            name=name,
            engine=type(transcription).__name__,
        )

    async def process_stream(self, request: ProcessStreamInboundDTO) -> TextStreamOutboundDTO:
        settings = StreamSettings(
            sample_rate=request.sample_rate,
            chunk_size=request.chunk_size,
            silence_threshold=request.silence_threshold,
            silence_limit_seconds=request.silence_limit_seconds,
        )
        text_stream = await self._transcription.transcribe_stream(settings, request.audio_stream)
        return TextStreamOutboundDTO(text_stream=text_stream)

    async def set_stream(self, request: SetStreamInboundDTO) -> None:
        settings = StreamSettings(
            sample_rate=request.sample_rate,
            chunk_size=request.chunk_size,
            silence_threshold=request.silence_threshold,
            silence_limit_seconds=request.silence_limit_seconds,
        )
        await self._cancel_stream_task()

        self._settings = settings
        queue: _TextQueue = asyncio.Queue()
        self._text_queue = queue
        self._stream_task = asyncio.create_task(
            self._forward_stream_to_queue(request, settings, queue)
        )
        try:
            await self._stream_task
        except asyncio.CancelledError:
            logger.info("Shared stream set request cancelled")
            raise
        logger.info("Shared stream completed")

    def current_settings(self) -> StreamSettings | None:
        return self._settings

    async def get_stream(self) -> TextStreamOutboundDTO:
        if self._text_queue is None:
            raise NoActiveStream("No active stream has been set")
        return TextStreamOutboundDTO(text_stream=self._queue_text_stream(self._text_queue))

    async def stop_stream(self) -> None:
        if self._stream_task and not self._stream_task.done():
            await self._cancel_stream_task()
        elif self._text_queue is not None:
            await self._text_queue.put(None)
        self._stream_task = None

    async def process_batch(self, request: ProcessBatchInboundDTO) -> BatchTranscriptionOutboundDTO:
        text = await self._transcription.transcribe_batch(request.audio_data, request.sample_rate)
        logger.info("Batch transcription completed", text_length=len(text))
        return BatchTranscriptionOutboundDTO(text=text)

    def is_available(self) -> bool:
        return self._transcription.is_available()

    async def _cancel_stream_task(self) -> None:
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                logger.info("Shared stream task cancelled")

    async def _forward_stream_to_queue(
        self, request: SetStreamInboundDTO, settings: StreamSettings, queue: _TextQueue
    ) -> None:
        async def live_audio_stream() -> AsyncIterator[bytes]:
            async for item in request.audio_stream:
                if isinstance(item, CompletedAudioSegment):
                    text = (
                        await self._transcription.transcribe_batch(
                            item.audio_data, settings.sample_rate
                        )
                    ).strip()
                    logger.info(
                        "Completed audio segment transcribed",
                        source_sequence=item.source_sequence,
                        text_length=len(text),
                    )
                    if text:
                        await queue.put(text)
                    continue
                yield item

        try:
            text_stream = await self._transcription.transcribe_stream(settings, live_audio_stream())
            async for text in text_stream:
                if text:
                    logger.info("Queued shared transcription", text_length=len(text))
                    await queue.put(text)
        except asyncio.CancelledError:
            logger.info("Shared stream forwarding task cancelled")
            raise
        except Exception as error:
            logger.exception("Shared stream forwarding failed")
            await queue.put(SharedStreamForwardingError(str(error)))
        finally:
            await queue.put(None)

    async def _queue_text_stream(self, queue: _TextQueue) -> AsyncIterator[str]:
        while True:
            item = await queue.get()
            try:
                if item is None:
                    logger.info("Shared text stream reached completion sentinel")
                    break
                if isinstance(item, Exception):
                    raise item
                yield item
            finally:
                queue.task_done()
