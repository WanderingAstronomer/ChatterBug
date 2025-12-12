"""Tests for batch transcription runner."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

from vociferous.app.batch import (
    BatchResult,
    BatchStats,
    BatchTranscriptionRunner,
    compute_batch_stats,
    generate_combined_transcript,
)


class TestBatchResult:
    """Tests for BatchResult dataclass."""

    def test_successful_result(self):
        """Can create a successful result."""
        result = BatchResult(
            source_file=Path("/path/to/audio.mp3"),
            success=True,
            transcript_text="Hello world.",
            output_path=Path("/output/audio_transcript.txt"),
            duration_s=5.5,
        )
        assert result.success is True
        assert result.transcript_text == "Hello world."
        assert result.error is None

    def test_failed_result(self):
        """Can create a failed result."""
        error = RuntimeError("Transcription failed")
        result = BatchResult(
            source_file=Path("/path/to/audio.mp3"),
            success=False,
            error=error,
            duration_s=1.0,
        )
        assert result.success is False
        assert result.error is error
        assert result.transcript_text is None


class TestBatchStats:
    """Tests for BatchStats dataclass."""

    def test_default_values(self):
        """Default stats are all zeros."""
        stats = BatchStats()
        assert stats.total_files == 0
        assert stats.successful == 0
        assert stats.failed == 0
        assert stats.total_duration_s == 0.0


class TestComputeBatchStats:
    """Tests for compute_batch_stats function."""

    def test_empty_results(self):
        """Empty results give zero stats."""
        stats = compute_batch_stats([])
        assert stats.total_files == 0
        assert stats.successful == 0
        assert stats.failed == 0

    def test_all_successful(self):
        """Counts successful results."""
        results = [
            BatchResult(source_file=Path("a.mp3"), success=True, duration_s=1.0),
            BatchResult(source_file=Path("b.mp3"), success=True, duration_s=2.0),
        ]
        stats = compute_batch_stats(results)
        assert stats.total_files == 2
        assert stats.successful == 2
        assert stats.failed == 0
        assert stats.total_duration_s == 3.0

    def test_mixed_results(self):
        """Counts both successful and failed."""
        results = [
            BatchResult(source_file=Path("a.mp3"), success=True, duration_s=1.0),
            BatchResult(source_file=Path("b.mp3"), success=False, duration_s=0.5),
            BatchResult(source_file=Path("c.mp3"), success=True, duration_s=2.0),
        ]
        stats = compute_batch_stats(results)
        assert stats.total_files == 3
        assert stats.successful == 2
        assert stats.failed == 1


class TestGenerateCombinedTranscript:
    """Tests for generate_combined_transcript function."""

    def test_combines_successful_results(self, tmp_path):
        """Combines transcripts from successful results."""
        results = [
            BatchResult(
                source_file=Path("a.mp3"),
                success=True,
                transcript_text="First transcript.",
            ),
            BatchResult(
                source_file=Path("b.mp3"),
                success=True,
                transcript_text="Second transcript.",
            ),
        ]
        
        output_path = tmp_path / "combined.txt"
        generate_combined_transcript(results, output_path)
        
        content = output_path.read_text()
        assert "First transcript." in content
        assert "Second transcript." in content
        assert "# a.mp3" in content
        assert "# b.mp3" in content

    def test_skips_failed_results(self, tmp_path):
        """Skips failed results."""
        results = [
            BatchResult(
                source_file=Path("a.mp3"),
                success=True,
                transcript_text="Good transcript.",
            ),
            BatchResult(
                source_file=Path("b.mp3"),
                success=False,
                error=RuntimeError("Failed"),
            ),
        ]
        
        output_path = tmp_path / "combined.txt"
        generate_combined_transcript(results, output_path)
        
        content = output_path.read_text()
        assert "Good transcript." in content
        assert "# b.mp3" not in content

    def test_without_filenames(self, tmp_path):
        """Can generate without file headers."""
        results = [
            BatchResult(
                source_file=Path("a.mp3"),
                success=True,
                transcript_text="Transcript text.",
            ),
        ]
        
        output_path = tmp_path / "combined.txt"
        generate_combined_transcript(results, output_path, include_filenames=False)
        
        content = output_path.read_text()
        assert "Transcript text." in content
        assert "# a.mp3" not in content


class TestBatchTranscriptionRunner:
    """Tests for BatchTranscriptionRunner class."""

    def test_init_with_defaults(self, tmp_path):
        """Initializes with sensible defaults."""
        runner = BatchTranscriptionRunner(
            files=[Path("a.mp3")],
            output_dir=tmp_path,
        )
        assert runner.parallel == 1
        assert runner.continue_on_error is True
        assert runner.daemon_mode == "always"
        assert runner.refine is True

    def test_init_with_options(self, tmp_path):
        """Accepts all options."""
        runner = BatchTranscriptionRunner(
            files=[Path("a.mp3"), Path("b.mp3")],
            output_dir=tmp_path,
            daemon_mode="never",
            parallel=4,
            continue_on_error=False,
            preprocess="clean",
            refine=False,
        )
        assert runner.parallel == 4
        assert runner.continue_on_error is False
        assert runner.daemon_mode == "never"
        assert runner.preprocess == "clean"
        assert runner.refine is False

    def test_parallel_min_is_one(self, tmp_path):
        """Parallel workers is at least 1."""
        runner = BatchTranscriptionRunner(
            files=[Path("a.mp3")],
            output_dir=tmp_path,
            parallel=0,
        )
        assert runner.parallel == 1

        runner = BatchTranscriptionRunner(
            files=[Path("a.mp3")],
            output_dir=tmp_path,
            parallel=-5,
        )
        assert runner.parallel == 1

    @patch("vociferous.config.get_segmentation_profile")
    @patch("vociferous.config.load_config")
    @patch("vociferous.app.batch.transcribe_file_workflow")
    def test_transcribe_single_success(
        self,
        mock_workflow,
        mock_load_config,
        mock_seg_profile,
        tmp_path,
    ):
        """_transcribe_single returns successful result."""
        # Setup mocks
        mock_config = Mock()
        mock_config.get_engine_profile.return_value = Mock()
        mock_load_config.return_value = mock_config
        mock_seg_profile.return_value = Mock()
        
        mock_result = Mock()
        mock_result.text = "Transcribed text."
        mock_workflow.return_value = mock_result

        # Create test file
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")
        
        # Create output directory (runner.run() normally does this)
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        runner = BatchTranscriptionRunner(
            files=[audio_file],
            output_dir=output_dir,
        )

        result = runner._transcribe_single(audio_file)

        assert result.success is True
        assert result.transcript_text == "Transcribed text."
        assert result.output_path is not None
        assert result.output_path.exists()

    @patch("vociferous.config.get_segmentation_profile")
    @patch("vociferous.config.load_config")
    @patch("vociferous.app.batch.transcribe_file_workflow")
    def test_transcribe_single_failure(
        self,
        mock_workflow,
        mock_load_config,
        mock_seg_profile,
        tmp_path,
    ):
        """_transcribe_single returns failed result on error."""
        mock_config = Mock()
        mock_config.get_engine_profile.return_value = Mock()
        mock_load_config.return_value = mock_config
        mock_seg_profile.return_value = Mock()
        
        mock_workflow.side_effect = RuntimeError("Engine error")

        runner = BatchTranscriptionRunner(
            files=[Path("test.mp3")],
            output_dir=tmp_path,
        )

        result = runner._transcribe_single(Path("test.mp3"))

        assert result.success is False
        assert result.error is not None
        assert "Engine error" in str(result.error)
