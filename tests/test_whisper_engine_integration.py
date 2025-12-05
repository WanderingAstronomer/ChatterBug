"""Integration tests for WhisperTurboEngine with faster-whisper (TDD approach)."""
import pytest
from unittest.mock import patch, MagicMock

from chatterbug.engines.whisper_turbo import WhisperTurboEngine
from chatterbug.domain.model import DEFAULT_WHISPER_MODEL, EngineConfig, TranscriptionOptions, AudioChunk
from chatterbug.engines.model_registry import normalize_model_name


def _config(**overrides) -> EngineConfig:
    return EngineConfig(**overrides)


def test_whisper_engine_model_initialization_without_cache_directory_param() -> None:
    """Test that WhisperModel is instantiated without cache_directory parameter.
    
    Regression test for: WhisperModel doesn't accept cache_directory or download_root.
    faster-whisper uses HF_HOME environment variable or standard HF cache.
    """
    config = _config(
        model_name="large-v3-turbo",
        device="cpu",
        compute_type="int8",
        params={"enable_batching": "true"},
    )
    
    # Mock the faster_whisper imports inside _lazy_model
    with patch("faster_whisper.WhisperModel") as mock_model_class:
        mock_instance = MagicMock()
        mock_model_class.return_value = mock_instance
        
        engine = WhisperTurboEngine(config)
        engine._lazy_model()
        
        # Verify WhisperModel was called WITHOUT cache_directory and WITH download_root
        mock_model_class.assert_called_once()
        call_kwargs = mock_model_class.call_args[1]
        assert "cache_directory" not in call_kwargs
        assert "download_root" in call_kwargs
        assert call_kwargs["device"] == "cpu"
        assert call_kwargs["compute_type"] == "int8"


def test_whisper_model_name_normalization_to_faster_whisper_format() -> None:
    """Test that model names are normalized to faster-whisper compatible format.
    
    Regression test for: Model normalization must map full HF names to faster-whisper short names.
    E.g., "openai/whisper-large-v3-turbo" -> "large-v3-turbo"
    """
    # Test default model (balanced turbo CT2)
    normalized = normalize_model_name("whisper_turbo", None)
    assert normalized == DEFAULT_WHISPER_MODEL, f"Expected faster-whisper format, got {normalized}"
    
    # Test alias resolution
    normalized = normalize_model_name("whisper_turbo", "turbo")
    assert normalized == "large-v3-turbo"
    
    # Test full name mapping
    normalized = normalize_model_name("whisper_turbo", "openai/whisper-large-v3-turbo")
    assert normalized == "large-v3-turbo"
    
    # Test other models
    normalized = normalize_model_name("whisper_turbo", "distil-large-v3")
    assert normalized == "distil-large-v3"
    
    normalized = normalize_model_name("whisper_turbo", "openai/whisper-medium")
    assert normalized == "medium"


def test_whisper_engine_batched_inference_pipeline_wrapping() -> None:
    """Test that BatchedInferencePipeline wraps the model when batching is enabled."""
    config = _config(
        model_name="large-v3-turbo",
        device="cpu",
        compute_type="int8",
        params={"enable_batching": "true", "batch_size": "8"},
    )
    
    with patch("faster_whisper.WhisperModel") as mock_model_class:
        with patch("faster_whisper.BatchedInferencePipeline") as mock_batched:
            mock_instance = MagicMock()
            mock_model_class.return_value = mock_instance
            mock_batched_instance = MagicMock()
            mock_batched.return_value = mock_batched_instance
            
            engine = WhisperTurboEngine(config)
            engine._lazy_model()
            
            # Verify BatchedInferencePipeline was used
            mock_batched.assert_called_once()
            assert engine._pipeline == mock_batched_instance
            assert engine._model == mock_instance


def test_whisper_engine_batching_disabled_uses_raw_model() -> None:
    """Test that raw model is used when batching is disabled."""
    config = _config(
        model_name="large-v3-turbo",
        device="cpu",
        compute_type="int8",
        params={"enable_batching": "false"},
    )
    
    with patch("faster_whisper.WhisperModel") as mock_model_class:
        with patch("faster_whisper.BatchedInferencePipeline") as mock_batched:
            mock_instance = MagicMock()
            mock_model_class.return_value = mock_instance
            
            engine = WhisperTurboEngine(config)
            engine._lazy_model()
            
            # Verify BatchedInferencePipeline was NOT used
            mock_batched.assert_not_called()
            assert engine._model == mock_instance


def test_whisper_engine_precision_mapping() -> None:
    """Test that compute_type is correctly set based on config.compute_type."""
    test_cases = [
        ("int8", "int8"),
        ("float16", "float16"),
        ("float32", "float32"),
        ("int8_float16", "int8_float16"),
    ]
    
    with patch("faster_whisper.WhisperModel") as mock_model_class:
        for compute_type, expected_precision in test_cases:
            config = _config(
                model_name="large-v3-turbo",
                device="cpu",
                compute_type=compute_type,
            )
            mock_instance = MagicMock()
            mock_model_class.return_value = mock_instance
            
            engine = WhisperTurboEngine(config)
            assert engine.precision == expected_precision


def test_whisper_engine_transcribe_with_streaming_chunks() -> None:
    """Test that transcribe_stream processes chunks incrementally."""
    config = _config(
        model_name="large-v3-turbo",
        device="cpu",
        compute_type="int8",
        params={"enable_batching": "true"},
    )
    
    chunks = [
        AudioChunk(samples=b"\x00" * 32000, sample_rate=16000, channels=1, start_s=0.0, end_s=1.0),
        AudioChunk(samples=b"\x00" * 32000, sample_rate=16000, channels=1, start_s=1.0, end_s=2.0),
        AudioChunk(samples=b"\x00" * 32000, sample_rate=16000, channels=1, start_s=2.0, end_s=3.0),
    ]
    
    with patch("faster_whisper.WhisperModel") as mock_model_class:
        with patch("faster_whisper.BatchedInferencePipeline") as mock_batched:
            mock_instance = MagicMock()
            mock_model_class.return_value = mock_instance
            mock_batched_instance = MagicMock()
            mock_batched.return_value = mock_batched_instance
            # Return (generator of segments, info object)
            mock_info = MagicMock()
            mock_instance.transcribe.return_value = (iter([]), mock_info)
            mock_batched_instance.transcribe.return_value = (iter([]), mock_info)
            
            engine = WhisperTurboEngine(config)
            engine._lazy_model()
            
            options = TranscriptionOptions()
            list(engine.transcribe_stream(chunks, options))
            
            # Verify transcribe was invoked (streaming may coalesce windows)
            assert mock_batched_instance.transcribe.call_count >= 1


def test_whisper_engine_error_handling_on_transcription_failure() -> None:
    """Test that transcription errors are wrapped in RuntimeError."""
    config = _config(
        model_name="large-v3-turbo",
        device="cpu",
        compute_type="int8",
    )
    
    chunks = [
        AudioChunk(samples=b"\x00" * 32000, sample_rate=16000, channels=1, start_s=0.0, end_s=1.0),
    ]
    
    with patch("faster_whisper.WhisperModel") as mock_model_class:
        mock_instance = MagicMock()
        mock_model_class.return_value = mock_instance
        mock_instance.transcribe.side_effect = Exception("Model inference failed")
        
        engine = WhisperTurboEngine(config)
        engine._lazy_model()
        
        options = TranscriptionOptions()
        with pytest.raises(RuntimeError, match="Model inference failed"):
            list(engine.transcribe_stream(chunks, options))
