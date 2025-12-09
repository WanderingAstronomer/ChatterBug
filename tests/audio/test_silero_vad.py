"""Tests for SileroVAD speech detection component."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vociferous.audio.silero_vad import SileroVAD


class TestSileroVADInitialization:
    """Test SileroVAD initialization."""
    
    def test_initialization_default_params(self) -> None:
        """SileroVAD initializes with default parameters."""
        vad = SileroVAD()
        assert vad.sample_rate == 16000
        assert vad.device == "cpu"
    
    def test_initialization_custom_sample_rate(self) -> None:
        """SileroVAD accepts custom sample rate."""
        vad = SileroVAD(sample_rate=8000)
        assert vad.sample_rate == 8000
    
    def test_initialization_custom_device(self) -> None:
        """SileroVAD accepts custom device."""
        vad = SileroVAD(device="cuda")
        assert vad.device == "cuda"


class TestSileroVADDetectSpeech:
    """Test detect_speech method."""
    
    def test_detect_speech_returns_timestamps(self, tmp_path: Path) -> None:
        """detect_speech returns list of timestamp dicts."""
        vad = SileroVAD()
        
        # Mock the internal VAD to return known spans
        mock_decoded = MagicMock()
        mock_decoded.samples = b"\x00\x00" * 16000  # 1 second of silence
        
        with patch.object(vad._vad, 'speech_spans', return_value=[(1600, 8000), (12000, 15000)]):
            with patch('vociferous.audio.decoder.FfmpegDecoder') as mock_decoder_cls:
                mock_decoder = MagicMock()
                mock_decoder.decode.return_value = mock_decoded
                mock_decoder_cls.return_value = mock_decoder
                
                # Create a dummy audio file
                audio_file = tmp_path / "test.wav"
                audio_file.write_bytes(b"RIFF" + b"\x00" * 100)
                
                timestamps = vad.detect_speech(audio_file)
        
        assert len(timestamps) == 2
        assert 'start' in timestamps[0]
        assert 'end' in timestamps[0]
        # Verify conversion from samples to seconds (16000 Hz sample rate)
        assert timestamps[0]['start'] == 1600 / 16000
        assert timestamps[0]['end'] == 8000 / 16000
    
    def test_detect_speech_empty_audio(self, tmp_path: Path) -> None:
        """detect_speech handles audio with no speech."""
        vad = SileroVAD()
        
        mock_decoded = MagicMock()
        mock_decoded.samples = b"\x00\x00" * 16000
        
        with patch.object(vad._vad, 'speech_spans', return_value=[]):
            with patch('vociferous.audio.decoder.FfmpegDecoder') as mock_decoder_cls:
                mock_decoder = MagicMock()
                mock_decoder.decode.return_value = mock_decoded
                mock_decoder_cls.return_value = mock_decoder
                
                audio_file = tmp_path / "silence.wav"
                audio_file.write_bytes(b"RIFF" + b"\x00" * 100)
                
                timestamps = vad.detect_speech(audio_file)
        
        assert timestamps == []


class TestSileroVADJSONCache:
    """Test JSON caching functionality."""
    
    def test_save_json_cache(self, tmp_path: Path) -> None:
        """detect_speech can save timestamps to JSON cache."""
        vad = SileroVAD()
        
        mock_decoded = MagicMock()
        mock_decoded.samples = b"\x00\x00" * 16000
        
        with patch.object(vad._vad, 'speech_spans', return_value=[(1600, 8000)]):
            with patch('vociferous.audio.decoder.FfmpegDecoder') as mock_decoder_cls:
                mock_decoder = MagicMock()
                mock_decoder.decode.return_value = mock_decoded
                mock_decoder_cls.return_value = mock_decoder
                
                audio_file = tmp_path / "audio.mp3"
                audio_file.write_bytes(b"ID3" + b"\x00" * 100)
                
                vad.detect_speech(audio_file, save_json=True)
        
        cache_file = tmp_path / "audio_vad_timestamps.json"
        assert cache_file.exists()
        
        with open(cache_file) as f:
            cached = json.load(f)
        
        assert len(cached) == 1
        assert cached[0]['start'] == 1600 / 16000
        assert cached[0]['end'] == 8000 / 16000
    
    def test_load_cached_timestamps_exists(self, tmp_path: Path) -> None:
        """load_cached_timestamps returns cached data when file exists."""
        audio_file = tmp_path / "lecture.wav"
        cache_file = tmp_path / "lecture_vad_timestamps.json"
        
        expected = [{'start': 1.5, 'end': 3.0}, {'start': 5.0, 'end': 8.5}]
        with open(cache_file, 'w') as f:
            json.dump(expected, f)
        
        result = SileroVAD.load_cached_timestamps(audio_file)
        
        assert result == expected
    
    def test_load_cached_timestamps_not_exists(self, tmp_path: Path) -> None:
        """load_cached_timestamps returns None when cache doesn't exist."""
        audio_file = tmp_path / "missing.wav"
        
        result = SileroVAD.load_cached_timestamps(audio_file)
        
        assert result is None
    
    def test_load_cached_timestamps_invalid_json(self, tmp_path: Path) -> None:
        """load_cached_timestamps returns None for invalid JSON."""
        audio_file = tmp_path / "broken.wav"
        cache_file = tmp_path / "broken_vad_timestamps.json"
        
        cache_file.write_text("not valid json {{{")
        
        result = SileroVAD.load_cached_timestamps(audio_file)
        
        assert result is None
