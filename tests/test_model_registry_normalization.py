"""Tests for model registry normalization fixes (TDD approach)."""
import pytest

from chatterbug.domain.model import DEFAULT_WHISPER_MODEL
from chatterbug.engines.model_registry import normalize_model_name


def test_normalize_whisper_model_full_name_to_short_format() -> None:
    """Test that full Hugging Face model names map to faster-whisper short names.
    
    Regression test: Model names from config need to be normalized to faster-whisper format.
    """
    # Full names should map to short names for faster-whisper compatibility
    assert normalize_model_name("whisper_turbo", "openai/whisper-large-v3-turbo") == "large-v3-turbo"
    assert normalize_model_name("whisper_turbo", "openai/whisper-medium") == "medium"
    assert normalize_model_name("whisper_turbo", "openai/whisper-small") == "small"
    assert normalize_model_name("whisper_turbo", "openai/whisper-base") == "base"
    assert normalize_model_name("whisper_turbo", "openai/whisper-tiny") == "tiny"
    assert normalize_model_name("whisper_turbo", "openai/whisper-large-v3") == "large-v3"
    assert normalize_model_name("whisper_turbo", "distil-whisper/distil-large-v3") == "distil-large-v3"


def test_normalize_whisper_model_aliases() -> None:
    """Test that common aliases resolve to faster-whisper compatible names."""
    # Aliases should resolve to CT2 format names
    assert normalize_model_name("whisper_turbo", "balanced") == DEFAULT_WHISPER_MODEL
    assert normalize_model_name("whisper_turbo", "turbo-ct2") == DEFAULT_WHISPER_MODEL
    assert normalize_model_name("whisper_turbo", "turbo") == "large-v3-turbo"
    assert normalize_model_name("whisper_turbo", "large-v3-turbo") == "large-v3-turbo"
    assert normalize_model_name("whisper_turbo", "large-v3") == "large-v3"
    assert normalize_model_name("whisper_turbo", "distil-large-v3") == "distil-large-v3"
    assert normalize_model_name("whisper_turbo", "medium") == "medium"
    assert normalize_model_name("whisper_turbo", "small") == "small"
    assert normalize_model_name("whisper_turbo", "base") == "base"
    assert normalize_model_name("whisper_turbo", "tiny") == "tiny"


def test_normalize_whisper_model_case_insensitive() -> None:
    """Test that model name resolution is case-insensitive."""
    assert normalize_model_name("whisper_turbo", "TURBO") == "large-v3-turbo"
    assert normalize_model_name("whisper_turbo", "Turbo") == "large-v3-turbo"
    assert normalize_model_name("whisper_turbo", "MEDIUM") == "medium"
    assert normalize_model_name("whisper_turbo", "Small") == "small"


def test_normalize_whisper_model_default() -> None:
    """Test that None or empty string returns default model in CT2 format."""
    default = normalize_model_name("whisper_turbo", None)
    assert default == DEFAULT_WHISPER_MODEL  # New default
    
    default = normalize_model_name("whisper_turbo", "")
    assert default == DEFAULT_WHISPER_MODEL


def test_normalize_voxtral_model_names() -> None:
    """Test Voxtral model name normalization."""
    assert normalize_model_name("voxtral", "voxtral-mini") == "mistralai/Voxtral-Mini-3B-2507"
    assert normalize_model_name("voxtral", "voxtral-small") == "mistralai/Voxtral-Small-24B-2507"
    assert normalize_model_name("voxtral", "mini") == "mistralai/Voxtral-Mini-3B-2507"
    assert normalize_model_name("voxtral", "small") == "mistralai/Voxtral-Small-24B-2507"
    
    default = normalize_model_name("voxtral", None)
    assert default == "mistralai/Voxtral-Mini-3B-2507"


def test_normalize_whisper_vllm_model_names() -> None:
    """Test Whisper vLLM model name normalization."""
    assert normalize_model_name("whisper_vllm", "turbo") == "openai/whisper-large-v3-turbo"
    assert normalize_model_name("whisper_vllm", "large-v3") == "openai/whisper-large-v3"
    assert normalize_model_name("whisper_vllm", None) == "openai/whisper-large-v3-turbo"


def test_normalize_unknown_model_name_passthrough() -> None:
    """Test that unknown model names are passed through unchanged."""
    # For non-whisper engines, unknown names should pass through
    result = normalize_model_name("voxtral", "custom/model-name")
    assert result == "custom/model-name"


def test_normalize_whisper_unknown_name_passthrough() -> None:
    """Test that unknown whisper model names are passed through (for custom/local models)."""
    # Even for whisper, unknown full names should pass through
    result = normalize_model_name("whisper_turbo", "custom/whisper-model")
    assert result == "custom/whisper-model"
    
    result = normalize_model_name("whisper_turbo", "local-model-path")
    assert result == "local-model-path"
