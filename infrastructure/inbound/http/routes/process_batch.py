from contracts.api.microservices.stt.process_batch import STTProcessBatchResponse
from fastapi import Request, status
from fastapi.responses import JSONResponse
from shared_logging import get_logger

from application.dtos.inbound.process_batch_inbound import ProcessBatchInboundDTO
from application.ports.inbound.stt_inbound_port import SttInboundPort
from infrastructure.inbound.http.response.http_envelope import failure, failure_message, success

logger = get_logger(__name__)

DEFAULT_SAMPLE_RATE = 16000


async def handle_process_batch(request: Request, sample_rate: int, inbound: SttInboundPort) -> JSONResponse:
    """POST /process/batch?sample_rate=: one 16-bit mono PCM buffer in the body, its text back. 400 on an empty body."""
    try:
        audio_data = await request.body()
        if not audio_data:
            logger.warning("Batch request rejected: empty audio body")
            return failure_message(
                "process_batch",
                "No audio data provided",
                status.HTTP_400_BAD_REQUEST,
                "No audio data provided",
            )
        result = await inbound.process_batch(
            ProcessBatchInboundDTO(audio_data=audio_data, sample_rate=sample_rate)
        )
    except Exception as error:
        return failure("process_batch", "Failed to process batch", error)
    return success(
        "process_batch",
        "Audio processed successfully",
        STTProcessBatchResponse(text=result.text),
    )
