"""Test TranscriptionResult domain type."""
import pytest

from chatterbug.domain.model import TranscriptSegment, TranscriptionResult


@pytest.fixture
def sample_segments() -> tuple[TranscriptSegment, ...]:
    """Create sample transcript segments."""
    return (
        TranscriptSegment(text="Hello", start_s=0.0, end_s=0.5, language="en", confidence=0.95),
        TranscriptSegment(text="world", start_s=0.5, end_s=1.0, language="en", confidence=0.93),
    )


def test_transcription_result_creation(sample_segments: tuple[TranscriptSegment, ...]) -> None:
    """Test creating a TranscriptionResult."""
    result = TranscriptionResult(
        text="Hello world",
        segments=sample_segments,
        model_name="openai/whisper-large-v3-turbo",
        device="cpu",
        precision="int8",
        engine="whisper_turbo",
        duration_s=1.0,
    )
    assert result.text == "Hello world"
    assert len(result.segments) == 2
    assert result.model_name == "openai/whisper-large-v3-turbo"
    assert result.device == "cpu"
    assert result.precision == "int8"
    assert result.engine == "whisper_turbo"
    assert result.duration_s == 1.0
    assert result.warnings == ()


def test_transcription_result_with_warnings(sample_segments: tuple[TranscriptSegment, ...]) -> None:
    """Test TranscriptionResult with warnings."""
    result = TranscriptionResult(
        text="Hello world",
        segments=sample_segments,
        model_name="openai/whisper-large-v3-turbo",
        device="cpu",
        precision="int8",
        engine="whisper_turbo",
        duration_s=1.0,
        warnings=("Warning 1", "Warning 2"),
    )
    assert len(result.warnings) == 2
    assert "Warning 1" in result.warnings
    assert "Warning 2" in result.warnings


def test_transcription_result_voxtral_engine(sample_segments: tuple[TranscriptSegment, ...]) -> None:
    """Test TranscriptionResult with Voxtral engine."""
    result = TranscriptionResult(
        text="Smart transcription",
        segments=sample_segments,
        model_name="mistralai/Voxtral-Mini-3B-2507",
        device="cuda",
        precision="float16",
        engine="voxtral_local",
        duration_s=2.5,
    )
    assert result.engine == "voxtral_local"
    assert "Voxtral" in result.model_name
    assert result.device == "cuda"


def test_transcription_result_whisper_vllm(sample_segments: tuple[TranscriptSegment, ...]) -> None:
    """Test TranscriptionResult with Whisper vLLM engine."""
    result = TranscriptionResult(
        text="vLLM transcription",
        segments=sample_segments,
        model_name="openai/whisper-large-v3",
        device="cuda",
        precision="bfloat16",
        engine="whisper_vllm",
        duration_s=2.0,
    )
    assert result.engine == "whisper_vllm"
    assert "whisper" in result.model_name


def test_transcription_result_immutable(sample_segments: tuple[TranscriptSegment, ...]) -> None:
    """Test TranscriptionResult is frozen (immutable)."""
    result = TranscriptionResult(
        text="test",
        segments=sample_segments,
        model_name="test",
        device="cpu",
        precision="int8",
        engine="whisper_turbo",
        duration_s=1.0,
    )
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        result.text = "modified"  # type: ignore[misc]


def test_transcription_result_empty_segments() -> None:
    """Test TranscriptionResult with no segments."""
    result = TranscriptionResult(
        text="",
        segments=(),
        model_name="test",
        device="cpu",
        precision="int8",
        engine="whisper_turbo",
        duration_s=0.0,
    )
    assert len(result.segments) == 0
    assert result.text == ""
    assert result.duration_s == 0.0


def test_transcription_result_gpu_device(sample_segments: tuple[TranscriptSegment, ...]) -> None:
    """Test TranscriptionResult with GPU device."""
    result = TranscriptionResult(
        text="GPU transcription",
        segments=sample_segments,
        model_name="openai/whisper-large-v3-turbo",
        device="cuda",
        precision="float16",
        engine="whisper_turbo",
        duration_s=0.5,
    )
    assert result.device == "cuda"
    assert result.precision == "float16"
