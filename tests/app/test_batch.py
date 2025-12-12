"""Tests for batch transcription runner.

This module tests the BatchTranscriptionRunner and related functions for
batch processing of audio files. Following the architecture's testing philosophy,
pure dataclass and utility function tests use direct instantiation, while
orchestration tests use lightweight stub engines instead of mocks.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from vociferous.app.batch import (
    BatchResult,
    BatchStats,
    BatchTranscriptionRunner,
    compute_batch_stats,
    generate_combined_transcript,
)

if TYPE_CHECKING:
    pass


# =============================================================================
# BatchResult Dataclass Tests
# =============================================================================


class TestBatchResult:
    """Tests for BatchResult dataclass validation and construction."""

    def test_successful_result(self) -> None:
        """Successful result has text and output path, no error."""
        result = BatchResult(
            source_file=Path("/path/to/audio.mp3"),
            success=True,
            transcript_text="Hello world.",
            output_path=Path("/output/audio_transcript.txt"),
            duration_s=5.5,
        )
        assert result.success is True
        assert result.transcript_text == "Hello world."
        assert result.output_path == Path("/output/audio_transcript.txt")
        assert result.duration_s == 5.5
        assert result.error is None

    def test_failed_result(self) -> None:
        """Failed result has error, no transcript text."""
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
        assert result.output_path is None


# =============================================================================
# BatchStats Dataclass Tests
# =============================================================================


class TestBatchStats:
    """Tests for BatchStats dataclass defaults and construction."""

    def test_explicit_values(self) -> None:
        """Can construct with explicit values."""
        stats = BatchStats(
            total_files=10,
            successful=8,
            failed=2,
            total_duration_s=120.5,
            audio_duration_s=600.0,
        )
        assert stats.total_files == 10
        assert stats.successful == 8
        assert stats.failed == 2
        assert stats.total_duration_s == 120.5
        assert stats.audio_duration_s == 600.0


# =============================================================================
# compute_batch_stats Function Tests
# =============================================================================


class TestComputeBatchStats:
    """Tests for compute_batch_stats utility function."""

    def test_empty_results_returns_zero_stats(self) -> None:
        """Empty results list yields zero stats."""
        stats = compute_batch_stats([])
        assert stats.total_files == 0
        assert stats.successful == 0
        assert stats.failed == 0
        assert stats.total_duration_s == 0.0

    def test_all_successful_results(self) -> None:
        """Counts all successful results correctly."""
        results = [
            BatchResult(source_file=Path("a.mp3"), success=True, duration_s=1.0),
            BatchResult(source_file=Path("b.mp3"), success=True, duration_s=2.0),
            BatchResult(source_file=Path("c.mp3"), success=True, duration_s=3.0),
        ]
        stats = compute_batch_stats(results)
        assert stats.total_files == 3
        assert stats.successful == 3
        assert stats.failed == 0
        assert stats.total_duration_s == 6.0

    def test_all_failed_results(self) -> None:
        """Counts all failed results correctly."""
        results = [
            BatchResult(source_file=Path("a.mp3"), success=False, duration_s=0.5),
            BatchResult(source_file=Path("b.mp3"), success=False, duration_s=0.3),
        ]
        stats = compute_batch_stats(results)
        assert stats.total_files == 2
        assert stats.successful == 0
        assert stats.failed == 2
        assert stats.total_duration_s == 0.8

    def test_mixed_success_and_failure(self) -> None:
        """Correctly separates successful and failed counts."""
        results = [
            BatchResult(source_file=Path("a.mp3"), success=True, duration_s=1.0),
            BatchResult(source_file=Path("b.mp3"), success=False, duration_s=0.5),
            BatchResult(source_file=Path("c.mp3"), success=True, duration_s=2.0),
            BatchResult(source_file=Path("d.mp3"), success=False, duration_s=0.2),
        ]
        stats = compute_batch_stats(results)
        assert stats.total_files == 4
        assert stats.successful == 2
        assert stats.failed == 2
        assert stats.total_duration_s == pytest.approx(3.7)


# =============================================================================
# generate_combined_transcript Function Tests
# =============================================================================


class TestGenerateCombinedTranscript:
    """Tests for generate_combined_transcript utility function."""

    def test_combines_successful_transcripts_with_headers(self, tmp_path: Path) -> None:
        """Successful results are combined with source file headers."""
        results = [
            BatchResult(
                source_file=Path("first.mp3"),
                success=True,
                transcript_text="First transcript content.",
            ),
            BatchResult(
                source_file=Path("second.mp3"),
                success=True,
                transcript_text="Second transcript content.",
            ),
        ]

        output_path = tmp_path / "combined.txt"
        returned_path = generate_combined_transcript(results, output_path)

        assert returned_path == output_path
        assert output_path.exists()

        content = output_path.read_text()
        assert "# first.mp3" in content
        assert "First transcript content." in content
        assert "# second.mp3" in content
        assert "Second transcript content." in content

    def test_skips_failed_results(self, tmp_path: Path) -> None:
        """Failed results are excluded from combined output."""
        results = [
            BatchResult(
                source_file=Path("good.mp3"),
                success=True,
                transcript_text="Good transcript.",
            ),
            BatchResult(
                source_file=Path("bad.mp3"),
                success=False,
                error=RuntimeError("Failed"),
            ),
            BatchResult(
                source_file=Path("also_good.mp3"),
                success=True,
                transcript_text="Also good transcript.",
            ),
        ]

        output_path = tmp_path / "combined.txt"
        generate_combined_transcript(results, output_path)

        content = output_path.read_text()
        assert "Good transcript." in content
        assert "Also good transcript." in content
        assert "bad.mp3" not in content

    def test_without_filenames(self, tmp_path: Path) -> None:
        """Can generate without source file headers."""
        results = [
            BatchResult(
                source_file=Path("audio.mp3"),
                success=True,
                transcript_text="Transcript without header.",
            ),
        ]

        output_path = tmp_path / "combined.txt"
        generate_combined_transcript(results, output_path, include_filenames=False)

        content = output_path.read_text()
        assert "Transcript without header." in content
        assert "# audio.mp3" not in content
        assert "audio.mp3" not in content

    def test_custom_separator(self, tmp_path: Path) -> None:
        """Uses custom separator between transcripts."""
        results = [
            BatchResult(
                source_file=Path("a.mp3"),
                success=True,
                transcript_text="First.",
            ),
            BatchResult(
                source_file=Path("b.mp3"),
                success=True,
                transcript_text="Second.",
            ),
        ]

        output_path = tmp_path / "combined.txt"
        generate_combined_transcript(
            results, output_path, include_filenames=False, separator="\n---\n"
        )

        content = output_path.read_text()
        assert "First." in content
        assert "---" in content
        assert "Second." in content

    def test_empty_results_creates_empty_file(self, tmp_path: Path) -> None:
        """Empty results list creates an empty output file."""
        output_path = tmp_path / "combined.txt"
        generate_combined_transcript([], output_path)

        assert output_path.exists()
        assert output_path.read_text() == ""

    def test_skips_results_with_none_transcript(self, tmp_path: Path) -> None:
        """Results with None transcript_text are skipped."""
        results = [
            BatchResult(
                source_file=Path("a.mp3"),
                success=True,
                transcript_text=None,  # Edge case: success but no text
            ),
            BatchResult(
                source_file=Path("b.mp3"),
                success=True,
                transcript_text="Has text.",
            ),
        ]

        output_path = tmp_path / "combined.txt"
        generate_combined_transcript(results, output_path)

        content = output_path.read_text()
        assert "Has text." in content
        assert "a.mp3" not in content


# =============================================================================
# BatchTranscriptionRunner Initialization Tests
# =============================================================================


class TestBatchTranscriptionRunnerInit:
    """Tests for BatchTranscriptionRunner initialization and configuration."""

    def test_init_with_required_args_only(self, tmp_path: Path) -> None:
        """Initializes with sensible defaults when only required args given."""
        runner = BatchTranscriptionRunner(
            files=[Path("audio.mp3")],
            output_dir=tmp_path,
        )
        assert runner.files == [Path("audio.mp3")]
        assert runner.output_dir == tmp_path
        assert runner.parallel == 1
        assert runner.continue_on_error is True
        assert runner.daemon_mode == "always"
        assert runner.refine is True
        assert runner.preprocess is None
        assert runner.engine_profile is None
        assert runner.segmentation_profile is None

    def test_init_with_all_options(self, tmp_path: Path) -> None:
        """Accepts and stores all configuration options."""
        files = [Path("a.mp3"), Path("b.mp3"), Path("c.mp3")]
        runner = BatchTranscriptionRunner(
            files=files,
            output_dir=tmp_path,
            daemon_mode="never",
            parallel=4,
            continue_on_error=False,
            preprocess="clean",
            refine=False,
        )
        assert runner.files == files
        assert runner.parallel == 4
        assert runner.continue_on_error is False
        assert runner.daemon_mode == "never"
        assert runner.preprocess == "clean"
        assert runner.refine is False

    def test_parallel_minimum_is_one(self, tmp_path: Path) -> None:
        """Parallel worker count is clamped to minimum of 1."""
        runner_zero = BatchTranscriptionRunner(
            files=[Path("a.mp3")],
            output_dir=tmp_path,
            parallel=0,
        )
        assert runner_zero.parallel == 1

        runner_negative = BatchTranscriptionRunner(
            files=[Path("a.mp3")],
            output_dir=tmp_path,
            parallel=-10,
        )
        assert runner_negative.parallel == 1

    def test_empty_file_list_allowed(self, tmp_path: Path) -> None:
        """Empty file list is allowed at init (validated at run time)."""
        runner = BatchTranscriptionRunner(
            files=[],
            output_dir=tmp_path,
        )
        assert runner.files == []

    def test_daemon_mode_values(self, tmp_path: Path) -> None:
        """Accepts valid daemon mode values."""
        for mode in ["never", "auto", "always"]:
            runner = BatchTranscriptionRunner(
                files=[Path("a.mp3")],
                output_dir=tmp_path,
                daemon_mode=mode,
            )
            assert runner.daemon_mode == mode


# =============================================================================
# BatchTranscriptionRunner._transcribe_single Tests
# =============================================================================


class TestBatchTranscriptionRunnerTranscribeSingle:
    """Tests for the _transcribe_single method.

    These tests use monkeypatch because the full transcription workflow requires
    loading heavy ML models. The architecture allows this for app-level
    orchestration tests where real file tests would be impractical.
    """

    def test_successful_transcription_returns_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Successful transcription returns BatchResult with text and output path."""
        # Create test audio file
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Mock the workflow and config loading
        class MockResult:
            text = "Transcribed content from audio."

        def mock_workflow(*args, **kwargs):
            return MockResult()

        def mock_load_config():
            return SimpleNamespace(
                default_engine_profile="default",
                engine_profiles={"default": None},
            )

        def mock_get_engine_profile(config, name=None):
            return "mock_profile"

        def mock_get_seg_profile(config):
            return "mock_seg_profile"

        monkeypatch.setattr(
            "vociferous.app.batch.transcribe_file_workflow", mock_workflow
        )
        monkeypatch.setattr("vociferous.config.load_config", mock_load_config)
        monkeypatch.setattr(
            "vociferous.config.get_engine_profile", mock_get_engine_profile
        )
        monkeypatch.setattr(
            "vociferous.config.get_segmentation_profile", mock_get_seg_profile
        )

        runner = BatchTranscriptionRunner(
            files=[audio_file],
            output_dir=output_dir,
        )

        result = runner._transcribe_single(audio_file)

        assert result.success is True
        assert result.transcript_text == "Transcribed content from audio."
        assert result.output_path is not None
        assert result.output_path.exists()
        assert result.output_path.read_text() == "Transcribed content from audio."
        assert result.duration_s > 0
        assert result.error is None

    def test_workflow_exception_returns_failed_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Workflow exception is caught and returned as failed BatchResult."""

        def mock_workflow(*args, **kwargs):
            raise RuntimeError("Engine initialization failed")

        def mock_load_config():
            return SimpleNamespace(
                default_engine_profile="default",
                engine_profiles={"default": None},
            )

        def mock_get_engine_profile(config, name=None):
            return "mock_profile"

        def mock_get_seg_profile(config):
            return "mock_seg_profile"

        monkeypatch.setattr(
            "vociferous.app.batch.transcribe_file_workflow", mock_workflow
        )
        monkeypatch.setattr("vociferous.config.load_config", mock_load_config)
        monkeypatch.setattr(
            "vociferous.config.get_engine_profile", mock_get_engine_profile
        )
        monkeypatch.setattr(
            "vociferous.config.get_segmentation_profile", mock_get_seg_profile
        )

        runner = BatchTranscriptionRunner(
            files=[Path("test.mp3")],
            output_dir=tmp_path,
        )

        result = runner._transcribe_single(Path("test.mp3"))

        assert result.success is False
        assert result.error is not None
        assert "Engine initialization failed" in str(result.error)
        assert result.transcript_text is None
        assert result.output_path is None
        assert result.duration_s > 0

    def test_output_file_uses_stem_suffix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Output file name is derived from source file stem."""
        audio_file = tmp_path / "my_podcast_episode.mp3"
        audio_file.write_bytes(b"fake audio")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        class MockResult:
            text = "Content."

        def mock_workflow(*args, **kwargs):
            return MockResult()

        def mock_load_config():
            return SimpleNamespace(
                default_engine_profile="default",
                engine_profiles={"default": None},
            )

        def mock_get_engine_profile(config, name=None):
            return "mock"

        def mock_get_seg_profile(config):
            return "mock"

        monkeypatch.setattr(
            "vociferous.app.batch.transcribe_file_workflow", mock_workflow
        )
        monkeypatch.setattr("vociferous.config.load_config", mock_load_config)
        monkeypatch.setattr(
            "vociferous.config.get_engine_profile", mock_get_engine_profile
        )
        monkeypatch.setattr(
            "vociferous.config.get_segmentation_profile", mock_get_seg_profile
        )

        runner = BatchTranscriptionRunner(
            files=[audio_file],
            output_dir=output_dir,
        )

        result = runner._transcribe_single(audio_file)

        assert result.output_path is not None
        assert result.output_path.name == "my_podcast_episode_transcript.txt"


# =============================================================================
# BatchTranscriptionRunner.run Tests
# =============================================================================


class TestBatchTranscriptionRunnerRun:
    """Tests for the run() orchestration method."""

    def test_creates_output_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """run() creates output directory if it doesn't exist."""
        output_dir = tmp_path / "nonexistent" / "nested" / "output"
        assert not output_dir.exists()

        # Mock to avoid actual transcription
        def mock_run_sequential(self, progress=None):
            return []

        monkeypatch.setattr(
            BatchTranscriptionRunner, "_run_sequential", mock_run_sequential
        )

        runner = BatchTranscriptionRunner(
            files=[],
            output_dir=output_dir,
            daemon_mode="never",  # Skip daemon check
        )
        runner.run()

        assert output_dir.exists()

    def test_uses_sequential_when_parallel_is_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """run() uses _run_sequential when parallel=1."""
        sequential_called = []

        def mock_run_sequential(self, progress=None):
            sequential_called.append(True)
            return []

        def mock_run_parallel(self, progress=None):
            raise AssertionError("Should not call parallel")

        monkeypatch.setattr(
            BatchTranscriptionRunner, "_run_sequential", mock_run_sequential
        )
        monkeypatch.setattr(
            BatchTranscriptionRunner, "_run_parallel", mock_run_parallel
        )

        runner = BatchTranscriptionRunner(
            files=[],
            output_dir=tmp_path,
            parallel=1,
            daemon_mode="never",
        )
        runner.run()

        assert sequential_called == [True]

    def test_uses_parallel_when_parallel_greater_than_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """run() uses _run_parallel when parallel>1."""
        parallel_called = []

        def mock_run_sequential(self, progress=None):
            raise AssertionError("Should not call sequential")

        def mock_run_parallel(self, progress=None):
            parallel_called.append(True)
            return []

        monkeypatch.setattr(
            BatchTranscriptionRunner, "_run_sequential", mock_run_sequential
        )
        monkeypatch.setattr(
            BatchTranscriptionRunner, "_run_parallel", mock_run_parallel
        )

        runner = BatchTranscriptionRunner(
            files=[],
            output_dir=tmp_path,
            parallel=4,
            daemon_mode="never",
        )
        runner.run()

        assert parallel_called == [True]
