"""TDD tests for WhisperTurboEngine - comprehensive API integration."""
import pytest
from unittest.mock import patch, MagicMock, call
from pathlib import Path

from vociferous.engines.whisper_turbo import WhisperTurboEngine
from vociferous.domain.model import DEFAULT_WHISPER_MODEL, EngineConfig, TranscriptionOptions, AudioChunk
from vociferous.sources import FileSource


def _config(**overrides) -> EngineConfig:
    return EngineConfig(**overrides)


class TestWhisperTurboInitialization:
    """Test engine initialization with correct parameters."""

    def test_init_with_default_config(self) -> None:
        """Engine initializes with sensible defaults."""
        config = _config()
        engine = WhisperTurboEngine(config)
        
        assert engine.model_name == DEFAULT_WHISPER_MODEL
        assert engine.device in {"cpu", "cuda"}
        assert engine.precision in {"int8", "int8_float16", "float16", "bfloat16"}
        assert engine.enable_batching is True
        assert engine.batch_size == 8
        assert engine.clean_disfluencies is True  # New default

    def test_init_model_name_normalization(self) -> None:
        """Engine normalizes model names to faster-whisper format."""
        config = _config(model_name="small")
        engine = WhisperTurboEngine(config)
        assert engine.model_name == "small"
        
        config = _config(model_name="turbo")
        engine = WhisperTurboEngine(config)
        assert engine.model_name == "large-v3-turbo"

    def test_init_batching_config_from_params(self) -> None:
        """Engine reads batching settings from config params."""
        config = _config(
            params={"enable_batching": "false", "batch_size": "16"}
        )
        engine = WhisperTurboEngine(config)
        
        assert engine.enable_batching is False
        assert engine.batch_size == 16

    def test_clean_disfluencies_default_enabled(self) -> None:
        """Engine has clean_disfluencies enabled by default."""
        config = _config()
        engine = WhisperTurboEngine(config)
        
        assert engine.clean_disfluencies is True

    def test_clean_disfluencies_can_be_disabled(self) -> None:
        """Engine respects explicit disable of clean_disfluencies."""
        config = _config(params={"clean_disfluencies": "false"})
        engine = WhisperTurboEngine(config)
        
        assert engine.clean_disfluencies is False


class TestWhisperTurboModelLoading:
    """Test lazy model loading and WhisperModel instantiation."""

    def test_lazy_model_loads_once(self) -> None:
        """Model is loaded once on first transcription, cached after."""
        config = _config(params={"enable_batching": "true"})
        engine = WhisperTurboEngine(config)
        
        with patch("faster_whisper.WhisperModel") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            
            engine._lazy_model()
            engine._lazy_model()  # Call again
            
            # Should only instantiate once
            assert mock_class.call_count == 1

    def test_whisper_model_instantiated_with_correct_params(self) -> None:
        """WhisperModel gets correct parameters."""
        config = _config(
            model_name="large-v3-turbo",
            device="cuda",
            compute_type="float16"
        )
        engine = WhisperTurboEngine(config)
        
        with patch("faster_whisper.WhisperModel") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            
            engine._lazy_model()
            
            # Check call arguments
            call_kwargs = mock_class.call_args[1]
            assert call_kwargs["device"] == "cuda"
            assert call_kwargs["compute_type"] == "float16"
            assert "download_root" in call_kwargs
            assert "cache_directory" not in call_kwargs
            assert "cache_dir" not in call_kwargs

    def test_batched_pipeline_wrapping(self) -> None:
        """BatchedInferencePipeline only gets model param."""
        config = _config(params={"enable_batching": "true"})
        engine = WhisperTurboEngine(config)
        
        with patch("faster_whisper.WhisperModel") as mock_model_class:
            with patch("faster_whisper.BatchedInferencePipeline") as mock_batched:
                mock_instance = MagicMock()
                mock_model_class.return_value = mock_instance
                mock_batched_instance = MagicMock()
                mock_batched.return_value = mock_batched_instance
                
                engine._lazy_model()
                
                batched_call_args = mock_batched.call_args[0]
                assert batched_call_args[0] == mock_instance
                batched_call_kwargs = mock_batched.call_args[1]
                assert batched_call_kwargs.get("batch_size", engine.batch_size) == engine.batch_size
                assert engine._pipeline == mock_batched_instance


class TestWhisperTurboTranscription:
    """Test transcription with proper API usage."""

    def test_transcribe_uses_default_beam_size_when_unset(self) -> None:
        """beam_size falls back to preset default when not provided."""
        config = _config(params={"enable_batching": "true"})
        engine = WhisperTurboEngine(config)
        
        with patch("faster_whisper.WhisperModel") as mock_class, patch(
            "faster_whisper.BatchedInferencePipeline"
        ) as mock_batched:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_batched_instance = MagicMock()
            mock_batched.return_value = mock_batched_instance
            mock_batched_instance.transcribe.return_value = (iter([]), MagicMock())

            engine._lazy_model()
            
            chunk = AudioChunk(
                samples=b"\x00\x01" * 16000,
                sample_rate=16000,
                channels=1,
                start_s=0.0,
                end_s=1.0
            )
            
            # Test with beam_size=None (default -> preset)
            options = TranscriptionOptions(beam_size=None)
            engine.start(options)
            engine.push_audio(chunk.samples, int(chunk.start_s * 1000))
            engine.flush()
            
            call_kwargs = mock_batched_instance.transcribe.call_args[1]
            assert call_kwargs["beam_size"] == engine.default_beam_size

    def test_transcribe_passes_beam_size_when_set(self) -> None:
        """beam_size passed when explicitly set."""
        config = _config(params={"enable_batching": "true"})
        engine = WhisperTurboEngine(config)
        
        with patch("faster_whisper.WhisperModel") as mock_class, patch(
            "faster_whisper.BatchedInferencePipeline"
        ) as mock_batched:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_batched_instance = MagicMock()
            mock_batched.return_value = mock_batched_instance
            mock_batched_instance.transcribe.return_value = (iter([]), MagicMock())

            engine._lazy_model()
            
            chunk = AudioChunk(
                samples=b"\x00\x01" * 16000,
                sample_rate=16000,
                channels=1,
                start_s=0.0,
                end_s=1.0
            )
            
            options = TranscriptionOptions(beam_size=10)
            engine.start(options)
            engine.push_audio(chunk.samples, int(chunk.start_s * 1000))
            engine.flush()
            
            call_kwargs = mock_batched_instance.transcribe.call_args[1]
            assert call_kwargs["beam_size"] == 10

    def test_transcribe_passes_temperature_default_when_unset(self) -> None:
        """temperature defaults to preset when not set."""
        config = _config(params={"enable_batching": "true"})
        engine = WhisperTurboEngine(config)
        
        with patch("faster_whisper.WhisperModel") as mock_class, patch(
            "faster_whisper.BatchedInferencePipeline"
        ) as mock_batched:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_batched_instance = MagicMock()
            mock_batched.return_value = mock_batched_instance
            mock_info = MagicMock()
            mock_batched_instance.transcribe.return_value = (iter([]), mock_info)

            engine._lazy_model()
            
            chunk = AudioChunk(
                samples=b"\x00\x01" * 16000,
                sample_rate=16000,
                channels=1,
                start_s=0.0,
                end_s=1.0
            )
            
            # Test with temperature=None
            options = TranscriptionOptions(temperature=None)
            engine.start(options)
            engine.push_audio(chunk.samples, int(chunk.start_s * 1000))
            engine.flush()
            
            call_kwargs = mock_batched_instance.transcribe.call_args[1]
            assert call_kwargs["temperature"] == engine.default_temperature

    def test_transcribe_passes_batch_size_param(self) -> None:
        """batch_size parameter passed to transcribe()."""
        config = _config(params={"batch_size": "16", "enable_batching": "true"})
        engine = WhisperTurboEngine(config)
        
        with patch("faster_whisper.WhisperModel") as mock_class, patch(
            "faster_whisper.BatchedInferencePipeline"
        ) as mock_batched:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_batched_instance = MagicMock()
            mock_batched.return_value = mock_batched_instance
            mock_info = MagicMock()
            mock_batched_instance.transcribe.return_value = (iter([]), mock_info)

            engine._lazy_model()
            
            chunk = AudioChunk(
                samples=b"\x00\x01" * 16000,
                sample_rate=16000,
                channels=1,
                start_s=0.0,
                end_s=1.0
            )
            
            options = TranscriptionOptions()
            engine.start(options)
            engine.push_audio(chunk.samples, int(chunk.start_s * 1000))
            engine.flush()
            
            call_kwargs = mock_batched_instance.transcribe.call_args[1]
            assert call_kwargs["batch_size"] == 16

    def test_batch_size_defaults_to_1_when_batching_disabled(self) -> None:
        """batch_size=1 when batching is disabled."""
        config = _config(params={"enable_batching": "false"})
        engine = WhisperTurboEngine(config)
        
        with patch("faster_whisper.WhisperModel") as mock_class, patch(
            "faster_whisper.BatchedInferencePipeline"
        ) as mock_batched:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_batched_instance = MagicMock()
            mock_batched.return_value = mock_batched_instance
            mock_instance.transcribe.return_value = (iter([]), MagicMock())

            engine._lazy_model()
            
            chunk = AudioChunk(
                samples=b"\x00\x01" * 16000,
                sample_rate=16000,
                channels=1,
                start_s=0.0,
                end_s=1.0
            )
            
            options = TranscriptionOptions()
            engine.start(options)
            engine.push_audio(chunk.samples, int(chunk.start_s * 1000))
            engine.flush()
            
            # When batching is disabled, batch_size should NOT be passed to model.transcribe()
            call_kwargs = mock_instance.transcribe.call_args[1]
            assert "batch_size" not in call_kwargs

    def test_transcribe_handles_vad_and_word_timestamps(self) -> None:
        """VAD and word_timestamps settings passed correctly."""
        config = _config(params={"word_timestamps": "true", "enable_batching": "true"})
        engine = WhisperTurboEngine(config)
        
        with patch("faster_whisper.WhisperModel") as mock_class, patch(
            "faster_whisper.BatchedInferencePipeline"
        ) as mock_batched:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_batched_instance = MagicMock()
            mock_batched.return_value = mock_batched_instance
            mock_batched_instance.transcribe.return_value = (iter([]), MagicMock())

            engine._lazy_model()
            
            chunk = AudioChunk(
                samples=b"\x00\x01" * 16000,
                sample_rate=16000,
                channels=1,
                start_s=0.0,
                end_s=1.0
            )
            
            options = TranscriptionOptions()
            engine.start(options)
            engine.push_audio(chunk.samples, int(chunk.start_s * 1000))
            engine.flush()
            
            call_kwargs = mock_batched_instance.transcribe.call_args[1]
            assert call_kwargs["vad_filter"] is True
            assert call_kwargs["word_timestamps"] is True
