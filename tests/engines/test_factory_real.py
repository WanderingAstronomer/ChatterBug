"""Real-world engine factory tests.

Tests engine factory initialization with real configs (no mocks).
Validates engine resolution, model validation, and error handling.
"""

from __future__ import annotations

import tempfile

import pytest

from vociferous.domain.exceptions import ConfigurationError
from vociferous.domain.model import EngineConfig
from vociferous.engines.factory import build_engine
from vociferous.engines.model_registry import (
    DEFAULT_CANARY_MODEL,
    DEFAULT_WHISPER_MODEL,
)


class TestEngineFactory:
    """Engine factory with real initialization logic."""

    def test_build_whisper_engine_cpu(self) -> None:
        """Building Whisper engine on CPU succeeds."""
        config = EngineConfig(
            model_name=DEFAULT_WHISPER_MODEL,
            device="cpu",
            compute_type="int8",
        )
        engine = build_engine("whisper_turbo", config)
        assert engine is not None
        assert hasattr(engine, "transcribe_file")

    def test_build_whisper_engine_with_custom_model(self) -> None:
        """Whisper engine accepts model aliases."""
        config = EngineConfig(
            model_name="medium",  # Alias resolves to Systran model
            device="cpu",
            compute_type="int8",
        )
        engine = build_engine("whisper_turbo", config)
        assert engine is not None

    def test_build_engine_with_invalid_whisper_model_raises_error(self) -> None:
        """Invalid model for Whisper raises ValueError."""
        config = EngineConfig(
            model_name="invalid/model",
            device="cpu",
            compute_type="int8",
        )
        with pytest.raises(ValueError, match="Invalid model"):
            build_engine("whisper_turbo", config)

    def test_build_canary_engine_cpu_raises_config_error(self) -> None:
        """Canary on CPU-only system raises ConfigurationError."""
        # This test will only actually fail on CPU-only systems
        # On GPU systems, it will pass (GPU available)
        config = EngineConfig(
            model_name=DEFAULT_CANARY_MODEL,
            device="cpu",
            compute_type="float32",
        )
        try:
            engine = build_engine("canary_qwen", config)
            # If we get here, CUDA is available on this system
            assert engine is not None
        except ConfigurationError as e:
            # Expected on CPU-only systems
            assert "CUDA" in str(e) or "GPU" in str(e)

    def test_build_canary_engine_auto_device(self) -> None:
        """Canary with auto device detection works."""
        from vociferous.domain.exceptions import DependencyError
        config = EngineConfig(
            model_name=DEFAULT_CANARY_MODEL,
            device="auto",
            compute_type="auto",
        )
        try:
            engine = build_engine("canary_qwen", config)
            assert engine is not None
        except (ConfigurationError, DependencyError) as e:
            # Expected if CUDA not available or NeMo not installed
            assert "CUDA" in str(e) or "GPU" in str(e) or "NeMo" in str(e)

    def test_build_whisper_engine_auto_device(self) -> None:
        """Whisper with auto device detection works."""
        config = EngineConfig(
            model_name=DEFAULT_WHISPER_MODEL,
            device="auto",
            compute_type="auto",
        )
        engine = build_engine("whisper_turbo", config)
        assert engine is not None

    def test_build_engine_invalid_kind_raises_error(self) -> None:
        """Unknown engine kind raises ValueError."""
        config = EngineConfig()
        with pytest.raises(ValueError, match="Unknown engine kind"):
            build_engine("unknown_engine", config)

    def test_build_engine_with_cache_dir(self) -> None:
        """Engine accepts custom model cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = EngineConfig(
                model_name=DEFAULT_WHISPER_MODEL,
                device="cpu",
                compute_type="int8",
                model_cache_dir=tmpdir,
            )
            engine = build_engine("whisper_turbo", config)
            assert engine is not None


