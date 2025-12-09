import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch

from vociferous.cli.helpers import build_audio_source
from vociferous.config.schema import AppConfig
from vociferous.domain.model import PreprocessingConfig
from vociferous.sources import FileSource, MemorySource


def _tone(sample_rate: int, duration_ms: int, amplitude: int = 10000) -> np.ndarray:
    samples = int(sample_rate * (duration_ms / 1000))
    return np.full(samples, amplitude, dtype=np.int16)


def _silence(sample_rate: int, duration_ms: int) -> np.ndarray:
    samples = int(sample_rate * (duration_ms / 1000))
    return np.zeros(samples, dtype=np.int16)


def test_build_audio_source_uses_memory_source_when_preprocessing_enabled_with_speech(
    tmp_path: Path,
) -> None:
    """When preprocessing is enabled and speech is detected, returns MemorySource."""
    # Create a temporary audio file
    audio_file = tmp_path / "audio.wav"
    audio_file.write_bytes(b"RIFF" + b"\x00" * 100)  # Dummy content
    
    cfg = AppConfig(preprocessing_enabled=True, chunk_ms=1234)
    
    # Mock the classes that are imported inside the function
    mock_vad_instance = MagicMock()
    mock_vad_instance.detect_speech.return_value = [{'start': 0.5, 'end': 2.0}]
    
    mock_condenser_instance = MagicMock()
    condensed_file = tmp_path / "condensed.wav"
    condensed_file.write_bytes(b"RIFF" + b"\x00" * 100)
    mock_condenser_instance.condense.return_value = [condensed_file]
    
    mock_decoder_instance = MagicMock()
    mock_decoder_instance.decode.return_value = MagicMock(samples=b"\x00\x00" * 1000)
    
    # Patch the audio module where the classes are imported from
    with patch.object(
        __import__('vociferous.audio', fromlist=['SileroVAD']),
        'SileroVAD',
        return_value=mock_vad_instance
    ), patch.object(
        __import__('vociferous.audio', fromlist=['FFmpegCondenser']),
        'FFmpegCondenser',
        return_value=mock_condenser_instance
    ), patch.object(
        __import__('vociferous.audio.decoder', fromlist=['FfmpegDecoder']),
        'FfmpegDecoder',
        return_value=mock_decoder_instance
    ):
        source = build_audio_source(audio_file, cfg)
    
    assert isinstance(source, MemorySource)
    assert source.chunk_ms == cfg.chunk_ms
    
    assert isinstance(source, MemorySource)
    assert source.chunk_ms == cfg.chunk_ms


def test_build_audio_source_defaults_to_file_source_when_disabled() -> None:
    cfg = AppConfig(preprocessing_enabled=False, chunk_ms=777)

    source = build_audio_source(Path("audio.wav"), cfg)

    assert isinstance(source, FileSource)
    assert source.chunk_ms == cfg.chunk_ms
