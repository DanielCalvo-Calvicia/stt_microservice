import pytest

from domain.errors import InvalidStreamSettings
from domain.operations.pcm import PcmChunkAligner
from domain.operations.silence import silence_boundary_chunks, silence_limit_chunks
from domain.value_objects.stream_settings import StreamSettings


def test_defaults_match_the_documented_values():
    settings = StreamSettings()
    assert (
        settings.sample_rate,
        settings.chunk_size,
        settings.silence_threshold,
        settings.silence_limit_seconds,
    ) == (16000, 1024, 150, 2.0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"sample_rate": 0},
        {"sample_rate": -1},
        {"chunk_size": 0},
        {"silence_threshold": -1},
        {"silence_limit_seconds": -0.1},
    ],
)
def test_invalid_settings_are_rejected(kwargs):
    with pytest.raises(InvalidStreamSettings):
        StreamSettings(**kwargs)


def test_invalid_settings_are_still_a_value_error():
    with pytest.raises(ValueError):
        StreamSettings(chunk_size=0)


def test_zero_threshold_and_zero_limit_are_allowed():
    StreamSettings(silence_threshold=0, silence_limit_seconds=0)


def test_silence_limit_is_measured_in_chunks():
    assert silence_limit_chunks(StreamSettings(16000, 1024, 150, 2.0)) == 31  # 15.625 * 2
    assert silence_limit_chunks(StreamSettings(16000, 1000, 150, 1.0)) == 16


def test_boundary_is_at_least_one_all_zero_chunk():
    chunks = silence_boundary_chunks(StreamSettings(16000, 1024, 150, 0.0))
    assert chunks == [b"\x00\x00" * 1024]


def test_boundary_covers_the_silence_limit():
    settings = StreamSettings(16000, 1024, 150, 2.0)
    chunks = silence_boundary_chunks(settings)
    assert len(chunks) == silence_limit_chunks(settings)
    assert all(chunk == b"\x00\x00" * 1024 for chunk in chunks)


def test_aligner_passes_whole_samples_through():
    assert PcmChunkAligner().align(b"\x01\x02\x03\x04") == b"\x01\x02\x03\x04"


def test_aligner_carries_an_odd_byte_to_the_next_chunk():
    aligner = PcmChunkAligner()
    assert aligner.align(b"\x01\x02\x03") == b"\x01\x02"
    assert aligner.has_pending_byte
    assert aligner.align(b"\x04\x05") == b"\x03\x04"
    assert aligner.has_pending_byte
    assert aligner.align(b"\x06") == b"\x05\x06"
    assert not aligner.has_pending_byte


def test_aligner_reports_and_drops_a_trailing_byte():
    aligner = PcmChunkAligner()
    aligner.align(b"\x01")
    assert aligner.drop_pending() is True
    assert aligner.drop_pending() is False
    assert aligner.align(b"\x02\x03") == b"\x02\x03"
