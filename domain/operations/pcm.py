SAMPLE_WIDTH_BYTES = 2  # 16-bit signed PCM


class PcmChunkAligner:
    """Re-cuts a byte stream into whole 16-bit samples.

    A network chunk can end in the middle of a sample; the odd trailing byte is held back and
    prepended to the next chunk so that no sample is ever split.
    """

    def __init__(self) -> None:
        self._pending = b""

    @property
    def has_pending_byte(self) -> bool:
        return bool(self._pending)

    def align(self, chunk: bytes) -> bytes:
        """Return ``chunk`` (with any held-back byte in front) minus a trailing odd byte."""
        if self._pending:
            chunk = self._pending + chunk
            self._pending = b""
        if len(chunk) % SAMPLE_WIDTH_BYTES == 0:
            return chunk
        self._pending = chunk[-1:]
        return chunk[:-1]

    def drop_pending(self) -> bool:
        """Discard the held-back byte (the stream ended mid-sample); True if there was one."""
        dropped = bool(self._pending)
        self._pending = b""
        return dropped
