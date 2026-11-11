import pytest

from domain.errors import InvalidAudioUtterance
from domain.value_objects.audio_utterance import AudioUtterance


def test_an_utterance_is_whole_16_bit_samples_at_a_positive_rate():
    utterance = AudioUtterance(b"\x01\x00\x02\x00", 8000)

    assert (utterance.audio, utterance.sample_rate) == (b"\x01\x00\x02\x00", 8000)
    assert AudioUtterance(b"").sample_rate == 16000


@pytest.mark.parametrize("rate", [0, -1])
def test_a_rate_that_is_not_positive_is_refused(rate):
    with pytest.raises(InvalidAudioUtterance):
        AudioUtterance(b"\x00\x00", rate)


def test_half_a_sample_is_refused_and_is_still_a_value_error():
    with pytest.raises(InvalidAudioUtterance) as error:
        AudioUtterance(b"\x00\x00\x01", 16000)

    assert isinstance(error.value, ValueError)
