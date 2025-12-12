"""Batch transcription runner for processing multiple audio files.

Provides parallel processing, error handling, and combined output
generation for batch transcription jobs.

Usage:
    from vociferous.app.batch import BatchTranscriptionRunner, BatchResult
    
    runner = BatchTranscriptionRunner(
        files=[Path("audio1.mp3"), Path("audio2.mp3")],
        output_dir=Path("transcripts"),
    )
    
    results = runner.run()
    
    for result in results:
        if result.success:
            print(f"{result.source_file.name}: {result.output_path}")
        else:
            print(f"{result.source_file.name}: FAILED - {result.error}")
"""

from __future__ import annotations

import concurrent.futures
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from vociferous.app.workflow import transcribe_file_workflow
from vociferous.domain.model import EngineProfile, SegmentationProfile
from vociferous.sources import FileSource

if TYPE_CHECKING:
    from vociferous.app.progress import ProgressTracker

logger = logging.getLogger(__name__)


@dataclass
class BatchResult:
    """Result of transcribing a single file in a batch.

    Attributes:
        source_file: Path to the original audio file
        success: Whether transcription succeeded
        transcript_text: The transcribed text (if successful)
        output_path: Path where transcript was saved (if successful)
        error: Exception that occurred (if failed)
        duration_s: Time taken to transcribe this file
    """

    source_file: Path
    success: bool
    transcript_text: str | None = None
    output_path: Path | None = None
    error: Exception | None = None
    duration_s: float = 0.0


@dataclass
class BatchStats:
    """Statistics for a batch transcription run.

    Attributes:
        total_files: Total number of files processed
        successful: Number of successful transcriptions
        failed: Number of failed transcriptions
        total_duration_s: Total time for the batch run
        audio_duration_s: Total audio duration processed
    """

    total_files: int = 0
    successful: int = 0
    failed: int = 0
    total_duration_s: float = 0.0
    audio_duration_s: float = 0.0


class BatchTranscriptionRunner:
    """Manages batch transcription with progress tracking and error handling.

    Supports sequential or parallel processing, daemon integration,
    and combined output generation.

    Args:
        files: List of audio files to transcribe
        output_dir: Directory for output transcripts
        engine_profile: Engine configuration profile
        segmentation_profile: VAD and chunking settings
        daemon_mode: Daemon mode (never, auto, always)
        parallel: Number of parallel workers (1 for sequential)
        continue_on_error: Continue processing if a file fails
        preprocess: Audio preprocessing preset
        refine: Whether to refine transcripts

    Example:
        runner = BatchTranscriptionRunner(
            files=[Path("a.mp3"), Path("b.mp3")],
            output_dir=Path("transcripts"),
            daemon_mode="always",
            parallel=2,
        )
        results = runner.run()
    """

    def __init__(
        self,
        files: list[Path],
        output_dir: Path,
        engine_profile: EngineProfile | None = None,
        segmentation_profile: SegmentationProfile | None = None,
        *,
        daemon_mode: str = "always",
        parallel: int = 1,
        continue_on_error: bool = True,
        preprocess: str | None = None,
        refine: bool = True,
    ) -> None:
        self.files = files
        self.output_dir = output_dir
        self.engine_profile = engine_profile
        self.segmentation_profile = segmentation_profile
        self.daemon_mode = daemon_mode
        self.parallel = max(1, parallel)
        self.continue_on_error = continue_on_error
        self.preprocess = preprocess
        self.refine = refine

    def run(
        self,
        progress: ProgressTracker | None = None,
    ) -> list[BatchResult]:
        """Execute batch transcription.

        Args:
            progress: Optional progress tracker for UI feedback

        Returns:
            List of BatchResult objects, one per input file
        """
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Ensure daemon is running if needed
        if self.daemon_mode in ["auto", "always"]:
            try:
                from vociferous.server import DaemonManager
                manager = DaemonManager()
                daemon_ready = manager.ensure_running(auto_start=self.daemon_mode == "always")
                if not daemon_ready and progress:
                    progress.print("⚠️ Daemon not available, using direct engine", style="yellow")
            except ImportError:
                pass

        # Choose sequential or parallel processing
        if self.parallel == 1:
            return self._run_sequential(progress)
        else:
            return self._run_parallel(progress)

    def _run_sequential(
        self,
        progress: ProgressTracker | None = None,
    ) -> list[BatchResult]:
        """Process files sequentially with progress tracking."""
        results: list[BatchResult] = []

        task_id = None
        if progress:
            task_id = progress.add_step(
                f"Batch transcription (0/{len(self.files)})",
                total=len(self.files),
            )

        for i, audio_file in enumerate(self.files, 1):
            if progress and task_id is not None:
                progress.update(
                    task_id,
                    description=f"[cyan]Transcribing {audio_file.name} ({i}/{len(self.files)})",
                    completed=i - 1,
                )

            result = self._transcribe_single(audio_file)
            results.append(result)

            if progress and task_id is not None:
                progress.advance(task_id)

                if result.success:
                    progress.print(f"  ✓ {audio_file.name}", style="green")
                else:
                    progress.print(f"  ✗ {audio_file.name}: {result.error}", style="red")

            # Stop on error if requested
            if not result.success and not self.continue_on_error:
                if progress:
                    progress.print(f"Stopping due to error: {result.error}", style="red")
                break

        if progress and task_id is not None:
            progress.complete(task_id)

        return results

    def _run_parallel(
        self,
        progress: ProgressTracker | None = None,
    ) -> list[BatchResult]:
        """Process files in parallel using ThreadPoolExecutor."""
        results: list[BatchResult] = []

        task_id = None
        if progress:
            task_id = progress.add_step(
                f"Batch transcription (parallel, {self.parallel} workers)",
                total=len(self.files),
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.parallel) as executor:
            # Submit all jobs
            future_to_file = {
                executor.submit(self._transcribe_single, f): f
                for f in self.files
            }

            # Collect results as they complete
            for completed, future in enumerate(concurrent.futures.as_completed(future_to_file), 1):
                audio_file = future_to_file[future]

                try:
                    result = future.result()
                except Exception as e:
                    result = BatchResult(
                        source_file=audio_file,
                        success=False,
                        error=e,
                    )

                results.append(result)

                if progress and task_id is not None:
                    progress.update(
                        task_id,
                        description=f"[cyan]Completed {completed}/{len(self.files)}",
                    )
                    progress.advance(task_id)

                    if result.success:
                        progress.print(f"  ✓ {audio_file.name}", style="green")
                    else:
                        progress.print(f"  ✗ {audio_file.name}: {result.error}", style="red")

        if progress and task_id is not None:
            progress.complete(task_id)

        return results

    def _transcribe_single(self, audio_file: Path) -> BatchResult:
        """Transcribe a single file and save output."""
        start_time = time.time()

        try:
            from vociferous.config import get_segmentation_profile, load_config

            # Load default profiles if not provided
            config = load_config()
            engine_profile = self.engine_profile or config.get_engine_profile()
            seg_profile = self.segmentation_profile or get_segmentation_profile(config)

            # Transcribe
            result = transcribe_file_workflow(
                source=FileSource(audio_file),
                engine_profile=engine_profile,
                segmentation_profile=seg_profile,
                refine=self.refine,
                use_daemon=(self.daemon_mode != "never"),
                daemon_mode=self.daemon_mode,
                preprocess=self.preprocess,
                progress=None,  # No nested progress for individual files
            )

            # Save output
            output_path = self.output_dir / f"{audio_file.stem}_transcript.txt"
            output_path.write_text(result.text)

            duration = time.time() - start_time

            return BatchResult(
                source_file=audio_file,
                success=True,
                transcript_text=result.text,
                output_path=output_path,
                duration_s=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Failed to transcribe {audio_file}: {e}")

            return BatchResult(
                source_file=audio_file,
                success=False,
                error=e,
                duration_s=duration,
            )


def generate_combined_transcript(
    results: list[BatchResult],
    output_path: Path,
    *,
    include_filenames: bool = True,
    separator: str = "\n\n",
) -> Path:
    """Generate a combined transcript from batch results.

    Args:
        results: List of batch results
        output_path: Path for combined transcript file
        include_filenames: Include source file names as headers
        separator: Separator between transcripts

    Returns:
        Path to the generated file
    """
    with open(output_path, "w") as f:
        successful = [r for r in results if r.success and r.transcript_text]

        for i, result in enumerate(successful):
            if include_filenames:
                f.write(f"# {result.source_file.name}\n\n")

            f.write(result.transcript_text.strip())

            if i < len(successful) - 1:
                f.write(separator)

    return output_path


def compute_batch_stats(results: list[BatchResult]) -> BatchStats:
    """Compute statistics for batch results.

    Args:
        results: List of batch results

    Returns:
        BatchStats with computed statistics
    """
    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful
    total_duration = sum(r.duration_s for r in results)

    return BatchStats(
        total_files=len(results),
        successful=successful,
        failed=failed,
        total_duration_s=total_duration,
    )
