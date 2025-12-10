"""Tests for refactored WhisperTurboEngine without internal VAD."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock, Mock
import numpy as np
import wave
import tempfile

from vociferous.domain.model import (
    EngineConfig,
    TranscriptionOptions,
    TranscriptSegment,
)
from vociferous.engines.whisper_turbo import WhisperTurboEngine


@pytest.fixture
def mock_engine_config():
    """Create a basic engine config for testing."""
    return EngineConfig(
        model_name="tiny",
        device="cpu",
        compute_type="int8",
    )


@pytest.fixture
def mock_transcription_options():
    """Create basic transcription options."""
    return TranscriptionOptions(
        language="en",
        beam_size=1,
    )


@pytest.fixture
def sample_wav_file(tmp_path):
    """Create a sample 16kHz mono PCM WAV file for testing."""
    wav_path = tmp_path / "test_audio.wav"
    
    # Generate 1 second of sine wave
    sample_rate = 16000
    duration = 1.0
    frequency = 440.0  # A4 note
    
    samples = np.arange(int(sample_rate * duration))
    audio = np.sin(2 * np.pi * frequency * samples / sample_rate)
    audio = (audio * 32767).astype(np.int16)
    
    # Write WAV file
    with wave.open(str(wav_path), 'wb') as wf:
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())
    
    return wav_path


def test_whisper_no_vad_parameter(mock_engine_config):
    """WhisperTurboEngine doesn't accept vad parameter anymore."""
    # Should not raise TypeError for missing vad parameter
    engine = WhisperTurboEngine(mock_engine_config)
    assert not hasattr(engine, 'vad')
    assert not hasattr(engine, '_vad')


def test_whisper_no_vad_filter_attribute(mock_engine_config):
    """WhisperTurboEngine no longer has vad_filter attribute."""
    engine = WhisperTurboEngine(mock_engine_config)
    assert not hasattr(engine, 'vad_filter')


def test_whisper_no_vad_config_params(mock_engine_config):
    """WhisperTurboEngine no longer has VAD configuration parameters."""
    engine = WhisperTurboEngine(mock_engine_config)
    
    # These VAD-related attributes should not exist
    vad_attrs = [
        'vad_threshold',
        'vad_neg_threshold',
        'vad_min_silence_ms',
        'vad_min_speech_ms',
        'vad_speech_pad_ms',
        'min_silence_ms',
        'tail_pad_ms',
    ]
    
    for attr in vad_attrs:
        assert not hasattr(engine, attr), f"Engine should not have {attr} attribute"


def test_whisper_transcribe_file_interface_exists(mock_engine_config):
    """WhisperTurboEngine has the new transcribe_file method."""
    engine = WhisperTurboEngine(mock_engine_config)
    assert hasattr(engine, 'transcribe_file')
    assert callable(engine.transcribe_file)


def test_whisper_load_audio_file(mock_engine_config, sample_wav_file):
    """_load_audio_file correctly loads WAV files."""
    engine = WhisperTurboEngine(mock_engine_config)
    
    audio_np = engine._load_audio_file(sample_wav_file)
    
    # Check output type and shape
    assert isinstance(audio_np, np.ndarray)
    assert audio_np.dtype == np.float32
    assert len(audio_np) == 16000  # 1 second at 16kHz
    assert -1.0 <= audio_np.min() <= audio_np.max() <= 1.0  # Normalized


def test_whisper_load_audio_file_validates_format(mock_engine_config, tmp_path):
    """_load_audio_file validates audio format."""
    engine = WhisperTurboEngine(mock_engine_config)
    
    # Test wrong sample rate
    wav_path = tmp_path / "wrong_rate.wav"
    with wave.open(str(wav_path), 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(8000)  # Wrong rate
        wf.writeframes(b'\x00\x00' * 1000)
    
    with pytest.raises(ValueError, match="Expected 16kHz"):
        engine._load_audio_file(wav_path)
    
    # Test wrong channels
    wav_path = tmp_path / "stereo.wav"
    with wave.open(str(wav_path), 'wb') as wf:
        wf.setnchannels(2)  # Stereo
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b'\x00\x00' * 1000)
    
    with pytest.raises(ValueError, match="Expected mono"):
        engine._load_audio_file(wav_path)


def test_whisper_transcribe_uses_vad_filter_false(mock_engine_config, mock_transcription_options):
    """Transcribe method always passes vad_filter=False to the model."""
    engine = WhisperTurboEngine(mock_engine_config)
    
    # Mock the model directly without calling _lazy_model
    mock_transcribe = MagicMock(return_value=([], None))
    engine._model = MagicMock()
    engine._model.transcribe = mock_transcribe
    
    # Call _transcribe
    audio_np = np.zeros(16000, dtype=np.float32)
    engine._options = mock_transcription_options
    engine._transcribe(audio_np)
    
    # Verify vad_filter=False was passed
    mock_transcribe.assert_called_once()
    call_kwargs = mock_transcribe.call_args[1]
    assert 'vad_filter' in call_kwargs
    assert call_kwargs['vad_filter'] is False


def test_whisper_backward_compatibility_streaming(mock_engine_config, mock_transcription_options):
    """Old streaming interface (start/push/flush/poll) still works."""
    engine = WhisperTurboEngine(mock_engine_config)
    
    # These methods should still exist for backward compatibility
    assert hasattr(engine, 'start')
    assert hasattr(engine, 'push_audio')
    assert hasattr(engine, 'flush')
    assert hasattr(engine, 'poll_segments')
    
    # Mock the model
    engine._model = MagicMock()
    engine._model.transcribe = MagicMock(return_value=([], None))
    
    # Should be able to use old interface
    engine.start(mock_transcription_options)
    engine.push_audio(b'\x00\x00' * 16000, timestamp_ms=0)
    engine.flush()
    segments = engine.poll_segments()
    
    assert isinstance(segments, list)


def test_whisper_metadata_property(mock_engine_config):
    """Engine metadata property returns correct information."""
    engine = WhisperTurboEngine(mock_engine_config)
    
    metadata = engine.metadata
    
    assert metadata.model_name is not None
    assert metadata.device == "cpu"
    assert metadata.precision == "int8"
