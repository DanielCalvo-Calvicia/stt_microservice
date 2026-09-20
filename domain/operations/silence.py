from domain.operations.pcm import SAMPLE_WIDTH_BYTES
from domain.value_objects.stream_settings import StreamSettings


def silence_limit_chunks(settings: StreamSettings) -> int:
    """How many consecutive silent chunks end an utterance."""
    chunks_per_second = settings.sample_rate / settings.chunk_size
    return int(chunks_per_second * settings.silence_limit_seconds)


def silence_boundary_chunks(settings: StreamSettings) -> list[bytes]:
    """Enough all-zero chunks to make a silence detector close the current utterance."""
    chunk_count = max(1, silence_limit_chunks(settings))
    silence_chunk = bytes(SAMPLE_WIDTH_BYTES) * settings.chunk_size
    return [silence_chunk] * chunk_count
