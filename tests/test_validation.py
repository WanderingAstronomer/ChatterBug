import pytest

from chatterbug.audio.validation import validate_pcm_chunk
from chatterbug.domain.exceptions import ConfigurationError


def test_validate_pcm_chunk_accepts_expected_size() -> None:
    data = b"\x00\x00" * 1600  # 100ms at 16kHz mono int16 => 1600 samples => 3200 bytes
    validate_pcm_chunk(data, sample_rate=16000, channels=1, chunk_ms=100, sample_width_bytes=2)


@pytest.mark.parametrize(
    "data,err_msg",
    [
        (b"", "Empty audio chunk"),
        (b"\x00\x00" * 10, "Unexpected chunk size"),
    ],
)
def test_validate_pcm_chunk_rejects_bad_sizes(data: bytes, err_msg: str) -> None:
    with pytest.raises(ConfigurationError, match=err_msg):
        validate_pcm_chunk(data, sample_rate=16000, channels=1, chunk_ms=100, sample_width_bytes=2)
