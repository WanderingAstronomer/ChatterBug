"""Real-world model registry resolution tests.

Tests model name normalization and validation without mocks.
Validates both Canary and Whisper model aliasing and defaults.
"""

from __future__ import annotations

import pytest

from vociferous.engines.model_registry import (
    DEFAULT_CANARY_MODEL,
    DEFAULT_WHISPER_MODEL,
    normalize_model_name,
)


class TestModelRegistry:
    """Model name normalization and validation."""

    # Canary model resolution
    def test_canary_default_model_when_none_provided(self) -> None:
        """None model name returns Canary default."""
        result = normalize_model_name("canary_qwen", None)
        assert result == DEFAULT_CANARY_MODEL

    def test_canary_explicit_model_accepted(self) -> None:
        """Explicit Canary model name accepted."""
        result = normalize_model_name("canary_qwen", DEFAULT_CANARY_MODEL)
        assert result == DEFAULT_CANARY_MODEL

    def test_canary_nvidia_prefix_accepted(self) -> None:
        """Canary models with nvidia/ prefix accepted."""
        model = "nvidia/canary-qwen-1b"
        result = normalize_model_name("canary_qwen", model)
        assert result == model

    def test_canary_rejects_invalid_model(self) -> None:
        """Invalid Canary model raises ValueError."""
        with pytest.raises(ValueError, match="Invalid model"):
            normalize_model_name("canary_qwen", "invalid/model")

    # Whisper model resolution
    def test_whisper_default_model_when_none_provided(self) -> None:
        """None model name returns Whisper default."""
        result = normalize_model_name("whisper_turbo", None)
        assert result == DEFAULT_WHISPER_MODEL

    def test_whisper_model_alias_large_v3_turbo(self) -> None:
        """Alias 'large-v3-turbo' resolves to default."""
        result = normalize_model_name("whisper_turbo", "large-v3-turbo")
        assert result == DEFAULT_WHISPER_MODEL

    def test_whisper_model_alias_large_v3(self) -> None:
        """Alias 'large-v3' resolves to Systran large-v3."""
        result = normalize_model_name("whisper_turbo", "large-v3")
        assert "large-v3" in result

    def test_whisper_model_alias_medium(self) -> None:
        """Alias 'medium' resolves to Systran medium."""
        result = normalize_model_name("whisper_turbo", "medium")
        assert "medium" in result

    def test_whisper_model_alias_small(self) -> None:
        """Alias 'small' resolves to Systran small."""
        result = normalize_model_name("whisper_turbo", "small")
        assert "small" in result



    def test_whisper_rejects_invalid_model(self) -> None:
        """Invalid Whisper model raises ValueError."""
        with pytest.raises(ValueError, match="Invalid model"):
            normalize_model_name("whisper_turbo", "nvidia/canary-qwen-2.5b")

    def test_whisper_detects_faster_whisper_model(self) -> None:
        """Faster-whisper models are detected and fall back to default."""
        # This should NOT raise, but instead return the default model
        result = normalize_model_name(
            "whisper_turbo", "deepdml/faster-whisper-large-v3-turbo-ct2"
        )
        assert result == DEFAULT_WHISPER_MODEL

    def test_whisper_detects_ctranslate_model(self) -> None:
        """CTranslate2 models are detected and fall back to default."""
        result = normalize_model_name(
            "whisper_turbo", "guillaumekln/faster-whisper-large-v2"
        )
        assert result == DEFAULT_WHISPER_MODEL

    # Cross-engine tests
    def test_unknown_engine_raises_error(self) -> None:
        """Unknown engine kind raises ValueError."""
        with pytest.raises(ValueError, match="Unknown engine kind"):
            normalize_model_name("unknown_engine", "some-model")

    def test_model_aliases_case_insensitive(self) -> None:
        """Model aliases are resolved case-insensitively."""
        result = normalize_model_name("whisper_turbo", "LARGE-V3-TURBO")
        assert result == DEFAULT_WHISPER_MODEL
