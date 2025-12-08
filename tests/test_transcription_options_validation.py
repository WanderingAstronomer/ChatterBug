"""Test TranscriptionOptions validation and param sanitization."""
import pytest

from vociferous.domain.model import TranscriptionOptions


def test_transcription_options_defaults() -> None:
    """Test default TranscriptionOptions values."""
    opts = TranscriptionOptions()
    assert opts.language == "en"
    assert opts.max_duration_s is None
    assert opts.beam_size is None
    assert opts.temperature is None
    assert opts.prompt is None
    assert opts.params == {}


def test_transcription_options_validates_beam_size() -> None:
    """Test beam_size validation rejects values < 1."""
    with pytest.raises(ValueError, match="beam_size must be >= 1"):
        TranscriptionOptions(beam_size=0)
    
    with pytest.raises(ValueError, match="beam_size must be >= 1"):
        TranscriptionOptions(beam_size=-1)
    
    # Valid values should work
    opts = TranscriptionOptions(beam_size=1)
    assert opts.beam_size == 1
    opts = TranscriptionOptions(beam_size=5)
    assert opts.beam_size == 5


def test_transcription_options_validates_temperature() -> None:
    """Test temperature validation rejects out-of-range values."""
    with pytest.raises(ValueError, match="temperature must be between 0.0 and 2.0"):
        TranscriptionOptions(temperature=-0.1)
    
    with pytest.raises(ValueError, match="temperature must be between 0.0 and 2.0"):
        TranscriptionOptions(temperature=2.1)
    
    # Valid boundary values should work
    opts = TranscriptionOptions(temperature=0.0)
    assert opts.temperature == 0.0
    opts = TranscriptionOptions(temperature=2.0)
    assert opts.temperature == 2.0
    opts = TranscriptionOptions(temperature=1.0)
    assert opts.temperature == 1.0


def test_transcription_options_validates_language() -> None:
    """Test language validation accepts ISO 639-1 codes and 'auto'."""
    # Valid cases
    assert TranscriptionOptions(language="en").language == "en"
    assert TranscriptionOptions(language="fr").language == "fr"
    assert TranscriptionOptions(language="es").language == "es"
    assert TranscriptionOptions(language="auto").language == "auto"
    assert TranscriptionOptions(language="EN").language == "en"  # Case insensitive

    # Invalid cases
    with pytest.raises(ValueError, match="Invalid language code"):
        TranscriptionOptions(language="eng")  # 3 letters
    
    with pytest.raises(ValueError, match="Invalid language code"):
        TranscriptionOptions(language="12")   # Numbers
    
    with pytest.raises(ValueError, match="Invalid language code"):
        TranscriptionOptions(language="")     # Empty


def test_transcription_options_validates_max_duration() -> None:
    """Test max_duration_s validation rejects non-positive values."""
    with pytest.raises(ValueError, match="max_duration_s must be positive"):
        TranscriptionOptions(max_duration_s=0.0)
    
    with pytest.raises(ValueError, match="max_duration_s must be positive"):
        TranscriptionOptions(max_duration_s=-1.0)
    
    # Valid values should work
    opts = TranscriptionOptions(max_duration_s=60.0)
    assert opts.max_duration_s == 60.0


def test_transcription_options_sanitizes_params() -> None:
    """Test empty/whitespace param values are removed."""
    opts = TranscriptionOptions(
        params={
            "max_new_tokens": "128",
            "empty": "",
            "spaces": "   ",
            "valid": "data",
        }
    )
    assert "max_new_tokens" in opts.params
    assert "valid" in opts.params
    assert "empty" not in opts.params
    assert "spaces" not in opts.params


def test_transcription_options_with_all_fields() -> None:
    """Test creating TranscriptionOptions with all fields set."""
    opts = TranscriptionOptions(
        language="es",
        max_duration_s=120.0,
        beam_size=3,
        temperature=0.5,
        prompt="Transcribe this audio",
        params={"word_timestamps": "true"},
    )
    assert opts.language == "es"
    assert opts.max_duration_s == 120.0
    assert opts.beam_size == 3
    assert opts.temperature == 0.5
    assert opts.prompt == "Transcribe this audio"
    assert opts.params["word_timestamps"] == "true"


def test_transcription_options_immutable() -> None:
    """Test TranscriptionOptions is frozen (immutable)."""
    opts = TranscriptionOptions()
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        opts.language = "fr"  # type: ignore[misc]
