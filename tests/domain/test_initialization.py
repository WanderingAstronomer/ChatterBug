"""Real-world configuration and domain model tests.

Tests configuration validation and domain model initialization without mocks.
Validates EngineConfig, RefinerConfig, and AppConfig with real values.
"""

from __future__ import annotations

import pytest

from vociferous.config.schema import AppConfig, ArtifactConfig
from vociferous.domain.model import (
    DEFAULT_CANARY_MODEL,
    EngineConfig,
    TranscriptionOptions,
)
from vociferous.refinement.base import RefinerConfig


class TestEngineConfig:
    """EngineConfig initialization and validation."""

    def test_engine_config_defaults(self) -> None:
        """EngineConfig has sensible defaults."""
        config = EngineConfig()
        assert config.model_name == DEFAULT_CANARY_MODEL
        assert config.device == "auto"
        assert config.compute_type == "auto"
        assert isinstance(config.params, dict)

    def test_engine_config_frozen(self) -> None:
        """EngineConfig is immutable after creation."""
        from pydantic import ValidationError
        config = EngineConfig()
        with pytest.raises(ValidationError):
            config.device = "cuda"  # type: ignore


class TestTranscriptionOptions:
    """TranscriptionOptions initialization and validation."""

    def test_transcription_options_defaults(self) -> None:
        """TranscriptionOptions has sensible defaults."""
        options = TranscriptionOptions()
        assert options.language == "en"
        assert isinstance(options.params, dict)

    def test_transcription_options_frozen(self) -> None:
        """TranscriptionOptions is immutable after creation."""
        from pydantic import ValidationError
        options = TranscriptionOptions()
        with pytest.raises(ValidationError):
            options.language = "fr"  # type: ignore


class TestRefinerConfig:
    """RefinerConfig initialization and validation."""

    def test_refiner_config_defaults(self) -> None:
        """RefinerConfig defaults to disabled."""
        config = RefinerConfig()
        assert config.enabled is False
        assert isinstance(config.params, dict)

    def test_refiner_config_frozen(self) -> None:
        """RefinerConfig is immutable after creation."""
        config = RefinerConfig()
        with pytest.raises(AttributeError):
            config.enabled = True  # type: ignore


class TestArtifactConfig:
    """ArtifactConfig initialization and validation."""

    def test_artifact_config_defaults(self) -> None:
        """ArtifactConfig has sensible defaults."""
        config = ArtifactConfig()
        assert config.cleanup_intermediates is True
        assert config.keep_on_error is True
        assert str(config.output_directory) == "."
        assert "{input_stem}" in config.naming_pattern




class TestAppConfig:
    """AppConfig initialization and validation."""

    def test_app_config_defaults(self) -> None:
        """AppConfig has sensible defaults."""
        config = AppConfig()
        assert config.model_name == DEFAULT_CANARY_MODEL
        assert config.engine == "canary_qwen"
        assert config.device == "auto"
        assert config.compute_type == "auto"
        assert isinstance(config.artifacts, ArtifactConfig)

    def test_app_config_compute_type_validation(self) -> None:
        """AppConfig validates compute type."""
        valid_types = ["auto", "int8", "int8_float16", "float16", "float32", "fp16", "fp32"]
        for comp_type in valid_types:
            config = AppConfig(compute_type=comp_type)
            assert config.compute_type == comp_type

    def test_app_config_invalid_compute_type_raises_error(self) -> None:
        """AppConfig rejects invalid compute types."""
        with pytest.raises(ValueError):
            AppConfig(compute_type="invalid_type")


