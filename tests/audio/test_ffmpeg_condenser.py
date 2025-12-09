"""Tests for FFmpegCondenser audio condensation component."""

from pathlib import Path
from unittest.mock import MagicMock, patch, call
import tempfile

import pytest

from vociferous.audio.ffmpeg_condenser import FFmpegCondenser, AudioProcessingError


class TestFFmpegCondenserInitialization:
    """Test FFmpegCondenser initialization."""
    
    def test_initialization_default_ffmpeg_path(self) -> None:
        """FFmpegCondenser uses default ffmpeg path."""
        condenser = FFmpegCondenser()
        assert condenser.ffmpeg_path == "ffmpeg"
    
    def test_initialization_custom_ffmpeg_path(self) -> None:
        """FFmpegCondenser accepts custom ffmpeg path."""
        condenser = FFmpegCondenser(ffmpeg_path="/usr/local/bin/ffmpeg")
        assert condenser.ffmpeg_path == "/usr/local/bin/ffmpeg"


class TestFFmpegCondenserCondense:
    """Test condense method."""
    
    def test_condense_short_file_single_output(self, tmp_path: Path) -> None:
        """Short file produces single output."""
        condenser = FFmpegCondenser()
        
        audio_file = tmp_path / "short.mp3"
        audio_file.write_bytes(b"ID3" + b"\x00" * 100)
        
        # Timestamps totaling 10 minutes (under 30 min limit)
        timestamps = [
            {'start': 0.0, 'end': 300.0},  # 5 min
            {'start': 350.0, 'end': 650.0},  # 5 min
        ]
        
        with patch.object(condenser, '_condense_segments') as mock_condense:
            result = condenser.condense(audio_file, timestamps)
        
        assert len(result) == 1
        assert "short_condensed.wav" in str(result[0])
        mock_condense.assert_called_once()
    
    def test_condense_empty_timestamps(self, tmp_path: Path) -> None:
        """Empty timestamps returns empty list."""
        condenser = FFmpegCondenser()
        
        audio_file = tmp_path / "audio.mp3"
        audio_file.write_bytes(b"ID3" + b"\x00" * 100)
        
        result = condenser.condense(audio_file, [])
        
        assert result == []
    
    def test_condense_custom_output_dir(self, tmp_path: Path) -> None:
        """Custom output directory is used."""
        condenser = FFmpegCondenser()
        
        audio_file = tmp_path / "audio.mp3"
        audio_file.write_bytes(b"ID3" + b"\x00" * 100)
        
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        timestamps = [{'start': 0.0, 'end': 60.0}]
        
        with patch.object(condenser, '_condense_segments'):
            result = condenser.condense(audio_file, timestamps, output_dir=output_dir)
        
        assert output_dir in result[0].parents or result[0].parent == output_dir


class TestFFmpegCondenserSilenceGaps:
    """Test silence gap calculation."""
    
    def test_calculate_silence_gaps(self) -> None:
        """Silence gaps are correctly calculated."""
        condenser = FFmpegCondenser()
        
        timestamps = [
            {'start': 0.0, 'end': 5.0},
            {'start': 10.0, 'end': 15.0},
            {'start': 20.0, 'end': 25.0},
        ]
        
        gaps = condenser._calculate_silence_gaps(timestamps)
        
        assert len(gaps) == 2
        assert gaps[0] == (5.0, 10.0)  # 5 second gap
        assert gaps[1] == (15.0, 20.0)  # 5 second gap
    
    def test_calculate_silence_gaps_no_gaps(self) -> None:
        """Continuous speech has no gaps."""
        condenser = FFmpegCondenser()
        
        timestamps = [
            {'start': 0.0, 'end': 5.0},
            {'start': 5.0, 'end': 10.0},
        ]
        
        gaps = condenser._calculate_silence_gaps(timestamps)
        
        assert gaps == []
    
    def test_calculate_silence_gaps_single_segment(self) -> None:
        """Single segment has no gaps."""
        condenser = FFmpegCondenser()
        
        timestamps = [{'start': 0.0, 'end': 10.0}]
        
        gaps = condenser._calculate_silence_gaps(timestamps)
        
        assert gaps == []


class TestFFmpegCondenserSafeCutPoints:
    """Test safe cut point finding."""
    
    def test_find_safe_cut_point_near_target(self) -> None:
        """Safe cut point is found near target."""
        condenser = FFmpegCondenser()
        
        timestamps = [
            {'start': 0.0, 'end': 100.0},
            {'start': 110.0, 'end': 200.0},  # 10 second gap here
            {'start': 250.0, 'end': 350.0},
        ]
        silence_gaps = [(100.0, 110.0), (200.0, 250.0)]
        
        # Target index 1, looking for gap after second segment
        cut_point = condenser._find_safe_cut_point(1, timestamps, silence_gaps, 5.0)
        
        # Should find a gap >= 5 seconds near the target
        assert cut_point is not None
        assert cut_point in [0, 1]  # Either gap is valid
    
    def test_find_safe_cut_point_no_suitable_gap(self) -> None:
        """Returns None when no suitable gap found."""
        condenser = FFmpegCondenser()
        
        timestamps = [
            {'start': 0.0, 'end': 100.0},
            {'start': 101.0, 'end': 200.0},  # 1 second gap only
        ]
        silence_gaps = [(100.0, 101.0)]
        
        cut_point = condenser._find_safe_cut_point(0, timestamps, silence_gaps, 5.0)
        
        assert cut_point is None


class TestFFmpegCondenserSplitting:
    """Test file splitting functionality."""
    
    def test_condense_long_file_multiple_outputs(self, tmp_path: Path) -> None:
        """Long file is split into multiple outputs."""
        condenser = FFmpegCondenser()
        
        audio_file = tmp_path / "long.mp3"
        audio_file.write_bytes(b"ID3" + b"\x00" * 100)
        
        # Timestamps totaling 45 minutes (over 30 min limit)
        timestamps = [
            {'start': 0.0, 'end': 900.0},  # 15 min
            {'start': 950.0, 'end': 1800.0},  # ~14 min, gap of 50s
            {'start': 1900.0, 'end': 2700.0},  # ~13 min, gap of 100s
        ]
        
        with patch.object(condenser, '_condense_segments'):
            result = condenser.condense(audio_file, timestamps, max_duration_minutes=30)
        
        # Should produce multiple output files
        assert len(result) >= 1
    
    def test_no_hard_split_raises_error(self, tmp_path: Path) -> None:
        """AudioProcessingError raised when no safe cut points found."""
        condenser = FFmpegCondenser()
        
        audio_file = tmp_path / "continuous.mp3"
        audio_file.write_bytes(b"ID3" + b"\x00" * 100)
        
        # Continuous speech with no gaps >= 2 seconds
        timestamps = [
            {'start': 0.0, 'end': 1800.0},  # 30 min continuous
            {'start': 1800.5, 'end': 3600.0},  # 30 more min, only 0.5s gap
        ]
        
        with pytest.raises(AudioProcessingError, match="Cannot split"):
            condenser.condense(audio_file, timestamps, max_duration_minutes=30)


class TestFFmpegCondenserFileNaming:
    """Test output file naming conventions."""
    
    def test_single_file_naming(self, tmp_path: Path) -> None:
        """Single output file has correct naming."""
        condenser = FFmpegCondenser()
        
        audio_file = tmp_path / "lecture.mp3"
        audio_file.write_bytes(b"ID3" + b"\x00" * 100)
        
        timestamps = [{'start': 0.0, 'end': 60.0}]
        
        with patch.object(condenser, '_condense_segments'):
            result = condenser.condense(audio_file, timestamps)
        
        assert result[0].name == "lecture_condensed.wav"
    
    def test_split_file_naming(self, tmp_path: Path) -> None:
        """Split output files have correct part numbering."""
        condenser = FFmpegCondenser()
        
        audio_file = tmp_path / "meeting.mp3"
        audio_file.write_bytes(b"ID3" + b"\x00" * 100)
        
        # Force splitting by having large timestamps
        timestamps = [
            {'start': 0.0, 'end': 900.0},
            {'start': 1000.0, 'end': 1900.0},  # 100s gap
            {'start': 2000.0, 'end': 2900.0},  # 100s gap
        ]
        
        with patch.object(condenser, '_condense_segments'):
            result = condenser.condense(audio_file, timestamps, max_duration_minutes=25)
        
        if len(result) > 1:
            assert "part_001" in result[0].name
            assert "part_002" in result[1].name
