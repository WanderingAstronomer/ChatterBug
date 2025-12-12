"""Tests for audio preprocessing module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from vociferous.audio.preprocessing import (
    AudioPreprocessor,
    PreprocessingConfig,
    preprocess_audio,
)


class TestPreprocessingConfig:
    """Tests for PreprocessingConfig dataclass."""

    def test_default_values(self):
        """Default config has no preprocessing enabled."""
        config = PreprocessingConfig()
        assert config.denoise is False
        assert config.normalize is False
        assert config.highpass_hz is None
        assert config.lowpass_hz is None
        assert config.volume_adjust_db is None
        assert config.needs_preprocessing() is False

    def test_from_preset_none(self):
        """'none' preset has no preprocessing."""
        config = PreprocessingConfig.from_preset("none")
        assert config.needs_preprocessing() is False

    def test_from_preset_basic(self):
        """'basic' preset enables normalization."""
        config = PreprocessingConfig.from_preset("basic")
        assert config.normalize is True
        assert config.denoise is False
        assert config.needs_preprocessing() is True

    def test_from_preset_clean(self):
        """'clean' preset enables denoise and normalize."""
        config = PreprocessingConfig.from_preset("clean")
        assert config.denoise is True
        assert config.normalize is True
        assert config.needs_preprocessing() is True

    def test_from_preset_phone(self):
        """'phone' preset has phone-specific filters."""
        config = PreprocessingConfig.from_preset("phone")
        assert config.denoise is True
        assert config.normalize is True
        assert config.highpass_hz == 300
        assert config.lowpass_hz == 3400

    def test_from_preset_podcast(self):
        """'podcast' preset optimized for podcasts."""
        config = PreprocessingConfig.from_preset("podcast")
        assert config.normalize is True
        assert config.highpass_hz == 80

    def test_from_preset_unknown_raises(self):
        """Unknown preset raises ValueError."""
        with pytest.raises(ValueError, match="Unknown preset"):
            PreprocessingConfig.from_preset("invalid_preset")

    def test_available_presets(self):
        """available_presets returns all preset names."""
        presets = PreprocessingConfig.available_presets()
        assert "none" in presets
        assert "basic" in presets
        assert "clean" in presets
        assert "phone" in presets
        assert "podcast" in presets

    def test_needs_preprocessing_true_cases(self):
        """needs_preprocessing returns True when any filter enabled."""
        assert PreprocessingConfig(denoise=True).needs_preprocessing() is True
        assert PreprocessingConfig(normalize=True).needs_preprocessing() is True
        assert PreprocessingConfig(highpass_hz=200).needs_preprocessing() is True
        assert PreprocessingConfig(lowpass_hz=3500).needs_preprocessing() is True
        assert PreprocessingConfig(volume_adjust_db=3.0).needs_preprocessing() is True


class TestAudioPreprocessor:
    """Tests for AudioPreprocessor class."""

    def test_needs_preprocessing_delegates_to_config(self):
        """needs_preprocessing delegates to config."""
        config = PreprocessingConfig()
        preprocessor = AudioPreprocessor(config)
        assert preprocessor.needs_preprocessing() is False

        config = PreprocessingConfig(normalize=True)
        preprocessor = AudioPreprocessor(config)
        assert preprocessor.needs_preprocessing() is True

    def test_build_filter_chain_normalize_only(self):
        """Filter chain for normalize only."""
        config = PreprocessingConfig(normalize=True)
        preprocessor = AudioPreprocessor(config)
        chain = preprocessor._build_filter_chain()
        assert "loudnorm" in chain

    def test_build_filter_chain_denoise(self):
        """Filter chain for denoise includes high/low pass."""
        config = PreprocessingConfig(denoise=True)
        preprocessor = AudioPreprocessor(config)
        chain = preprocessor._build_filter_chain()
        assert "highpass" in chain
        assert "lowpass" in chain

    def test_build_filter_chain_explicit_frequencies(self):
        """Explicit frequency filters are used."""
        config = PreprocessingConfig(highpass_hz=500, lowpass_hz=4000)
        preprocessor = AudioPreprocessor(config)
        chain = preprocessor._build_filter_chain()
        assert "highpass=f=500" in chain
        assert "lowpass=f=4000" in chain

    def test_build_filter_chain_volume_adjust(self):
        """Volume adjustment is applied."""
        config = PreprocessingConfig(volume_adjust_db=6.0)
        preprocessor = AudioPreprocessor(config)
        chain = preprocessor._build_filter_chain()
        assert "volume=6.0dB" in chain

    def test_describe_filters(self):
        """Filter description is human-readable."""
        config = PreprocessingConfig(denoise=True, normalize=True)
        preprocessor = AudioPreprocessor(config)
        description = preprocessor._describe_filters()
        assert "noise reduction" in description
        assert "normalization" in description

    @patch("vociferous.audio.preprocessing.shutil.which")
    def test_preprocess_returns_input_if_no_processing(self, mock_which):
        """Returns input path if no preprocessing needed."""
        mock_which.return_value = "/usr/bin/ffmpeg"
        config = PreprocessingConfig()
        preprocessor = AudioPreprocessor(config)
        
        input_path = Path("/tmp/input.wav")
        output_path = Path("/tmp/output.wav")
        
        result = preprocessor.preprocess(input_path, output_path)
        assert result == input_path

    @patch("vociferous.audio.preprocessing.subprocess.run")
    @patch("vociferous.audio.preprocessing.shutil.which")
    def test_preprocess_calls_ffmpeg(self, mock_which, mock_run):
        """Preprocessing calls FFmpeg with correct filters."""
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = Mock(returncode=0)
        
        config = PreprocessingConfig(normalize=True)
        preprocessor = AudioPreprocessor(config)
        
        input_path = Path("/tmp/input.wav")
        output_path = Path("/tmp/output.wav")
        
        result = preprocessor.preprocess(input_path, output_path)
        
        assert result == output_path
        mock_run.assert_called_once()
        
        # Check FFmpeg was called with the right arguments
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "ffmpeg" in cmd[0]
        assert "-af" in cmd
        assert str(input_path) in cmd
        assert str(output_path) in cmd


class TestPreprocessAudioConvenience:
    """Tests for preprocess_audio convenience function."""

    @patch("vociferous.audio.preprocessing.AudioPreprocessor.preprocess")
    def test_preprocess_audio_uses_preset(self, mock_preprocess):
        """preprocess_audio creates config from preset."""
        mock_preprocess.return_value = Path("/tmp/output.wav")
        
        input_path = Path("/tmp/input.wav")
        output_path = Path("/tmp/output.wav")
        
        preprocess_audio(input_path, output_path, preset="none")
        
        # Should return input since "none" preset has no processing
        # But mock overrides the return value
        mock_preprocess.assert_called_once_with(input_path, output_path, None)
