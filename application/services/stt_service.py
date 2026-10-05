import asyncio
from collections.abc import AsyncIterator

from shared_logging import get_logger

from application.dtos.batch_transcription_outbound import BatchTranscriptionOutboundDTO
from application.dtos.process_batch_inbound import ProcessBatchInboundDTO
from application.dtos.process_stream_inbound import ProcessStreamInboundDTO
from application.dtos.set_stream_inbound import SetStreamInboundDTO
from application.dtos.text_stream_outbound import TextStreamOutboundDTO
from application.errors import NoActiveStream, SharedStreamForwardingError
from application.ports.inbound.stt_transcription_port import SttTranscriptionPort
from application.ports.outbound.transcription_port import TranscriptionPort
from domain.value_objects.audio_utterance import AudioUtterance
from domain.value_objects.utterance import Utterance

logger = get_logger(__name__)

_TextQueue = asyncio.Queue[str | Utterance | Exception | None]


class SttService(SttTranscriptionPort):
    """Orchestrates the speech-to-text use cases. Business rules live in the domain.

    It receives finished utterances (the microphone cuts them, STT does no silence detection) and
    transcribes each one. With ``with_audio`` the shared stream yields ``Utterance`` items (the text
    plus the audio it came from): the wake-phrase gate. Otherwise it yields plain text.
    """

    def __init__(
        self, transcription: TranscriptionPort, name: str = "stt_service", *, with_audio: bool = False
    ) -> None:
        self.name = name
        self._with_audio = with_audio
        self._transcription = transcription
        self._text_queue: _TextQueue | None = None
        self._stream_task: asyncio.Task[None] | None = None
        logger.info("SttService initialized", name=name, engine=type(transcription).__name__)

    async def process_stream(self, request: ProcessStreamInboundDTO) -> TextStreamOutboundDTO:
        return TextStreamOutboundDTO(text_stream=self._transcribed(request.utterances))

    async def set_stream(self, request: SetStreamInboundDTO) -> None:
        await self._cancel_stream_task()

        queue: _TextQueue = asyncio.Queue()
        self._text_queue = queue
        self._stream_task = asyncio.create_task(self._forward_stream_to_queue(request, queue))
        try:
            await self._stream_task
        except asyncio.CancelledError:
            logger.info("Shared stream set request cancelled")
            raise
        logger.info("Shared stream completed")

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

    async def _transcribed(self, utterances: AsyncIterator[AudioUtterance]) -> AsyncIterator[str | Utterance]:
        """The text of each utterance, as it arrives; an utterance with no speech in it gives nothing."""
        async for utterance in utterances:
            text = (
                await self._transcription.transcribe_batch(utterance.audio, utterance.sample_rate)
            ).strip()
            logger.info(
                "Utterance transcribed",
                text_length=len(text),
                audio_bytes=len(utterance.audio),
                sample_rate=utterance.sample_rate,
            )
            if text:
                yield Utterance(text, utterance.audio) if self._with_audio else text

    async def _forward_stream_to_queue(self, request: SetStreamInboundDTO, queue: _TextQueue) -> None:
        try:
            async for item in self._transcribed(request.utterances):
                await queue.put(item)
        except asyncio.CancelledError:
            logger.info("Shared stream forwarding task cancelled")
            raise
        except Exception as error:
            logger.exception("Shared stream forwarding failed")
            await queue.put(SharedStreamForwardingError(str(error)))
        finally:
            await queue.put(None)

    async def _queue_text_stream(self, queue: _TextQueue) -> AsyncIterator[str | Utterance]:
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
