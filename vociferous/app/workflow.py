"""Batch transcription workflows (no sessions, no arbiters)."""

from __future__ import annotations

import wave
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import replace
from pathlib import Path

# Import progress tracking (use TYPE_CHECKING to avoid circular imports)
from typing import TYPE_CHECKING

from vociferous.cli.components.condenser import CondenserComponent
from vociferous.cli.components.decoder import DecoderComponent
from vociferous.cli.components.vad import VADComponent
from vociferous.config.schema import ArtifactConfig
from vociferous.domain.model import (
    EngineConfig,
    EngineKind,
    EngineMetadata,
    EngineProfile,
    SegmentationProfile,
    TranscriptionEngine,
    TranscriptionOptions,
    TranscriptionResult,
    TranscriptSegment,
)
from vociferous.engines.factory import build_engine
from vociferous.sources import FileSource, Source

if TYPE_CHECKING:
    from vociferous.app.progress import TranscriptionProgress


def _segments_to_text(segments: Iterable[TranscriptSegment]) -> str:
    """Join segment text into a single transcript string."""
    return " ".join(seg.text.strip() for seg in segments).strip()


def _offset_segments(segments: Iterable[TranscriptSegment], offset: float) -> list[TranscriptSegment]:
    """Shift segment timings by offset seconds."""
    if offset == 0:
        return list(segments)
    return [
        replace(seg, start=seg.start + offset, end=seg.end + offset)
        for seg in segments
    ]


def _wav_duration(path: Path) -> float:
    """Return WAV duration in seconds (mono/16k enforced upstream)."""
    with wave.open(str(path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
    return frames / rate if rate else 0.0


class EngineWorker:
    """In-process engine worker that keeps a single engine instance warm.
    
    Supports lazy loading and daemon integration - the local engine is only
    loaded if the daemon is not running or use_daemon is False.
    
    Daemon modes:
        - "never": Never use daemon, always use local engine
        - "auto": Use daemon if running, don't auto-start
        - "always": Use daemon and auto-start if not running
    """

    def __init__(
        self,
        profile: EngineProfile,
        *,
        engine: TranscriptionEngine | None = None,
        use_daemon: bool = False,
        daemon_mode: str = "auto",  # "never", "auto", "always"
        progress: TranscriptionProgress | None = None,
    ) -> None:
        self.profile = profile
        self._provided_engine = engine
        self._engine: TranscriptionEngine | None = engine
        self._warnings: list[str] = []
        
        # Handle legacy use_daemon parameter
        if not use_daemon:
            self._daemon_mode = "never"
        else:
            self._daemon_mode = daemon_mode
        
        self._daemon_checked = False
        self._daemon_available = False
        self._used_daemon = False  # Track if daemon was actually used
        self._progress = progress
        
        # Only load engine immediately if one was provided
        # Otherwise, defer to first use to allow daemon check
        if engine is not None:
            self._engine = engine

    def _check_daemon(self) -> bool:
        """Check if daemon is available (cached), auto-starting if configured."""
        if self._daemon_checked:
            return self._daemon_available
        
        self._daemon_checked = True
        
        if self._daemon_mode == "never":
            self._daemon_available = False
            return False
            
        try:
            from vociferous.server import DaemonManager
            
            manager = DaemonManager()
            
            if self._daemon_mode == "always":
                # Auto-start if not running
                self._daemon_available = manager.ensure_running(
                    auto_start=True,
                    progress=self._progress,
                )
            else:
                # "auto" mode - just check, don't start
                self._daemon_available = manager.is_running()
            
            if self._daemon_available:
                import logging
                logging.getLogger(__name__).info("Daemon detected, will use for transcription")
                
        except ImportError:
            self._daemon_available = False
        
        return self._daemon_available

    def _ensure_engine(self) -> TranscriptionEngine:
        """Lazily load the engine if needed."""
        if self._engine is None:
            self._engine = build_engine(self.profile.kind, self.profile.config)
        return self._engine

    @property
    def metadata(self) -> EngineMetadata:
        """Get engine metadata.

        If daemon was used, returns metadata based on profile config.
        Otherwise, loads the engine and gets its metadata.
        """
        if self._used_daemon:
            # Return metadata based on what we know from config
            return EngineMetadata(
                model_name=self.profile.config.model_name or "nvidia/canary-qwen-2.5b",
                device="daemon",
                precision=self.profile.config.compute_type or "fp16",
            )
        return self._ensure_engine().metadata

    @property
    def warnings(self) -> tuple[str, ...]:
        return tuple(self._warnings)

    def transcribe(self, audio_path: Path) -> list[TranscriptSegment]:
        """Transcribe a single audio file."""
        # Try daemon first if enabled
        if self._check_daemon():
            try:
                from vociferous.server import transcribe_via_daemon
                segments = transcribe_via_daemon(audio_path, self.profile.options.language)
                if segments is not None:
                    self._used_daemon = True
                    return segments
            except Exception:
                pass  # Fallback to local engine
        
        return self._ensure_engine().transcribe_file(Path(audio_path), self.profile.options)

    def refine_text(self, text: str, instructions: str | None = None) -> str:
        """Refine transcript text."""
        # Try daemon first if enabled
        if self._check_daemon():
            try:
                from vociferous.server import refine_via_daemon
                refined = refine_via_daemon(text, instructions)
                if refined is not None:
                    return str(refined)
            except Exception:
                pass  # Fallback to local engine

        engine = self._ensure_engine()
        if hasattr(engine, "refine_text"):
            result: str = engine.refine_text(text, instructions)
            return result
        return text

    def refine_segments(
        self,
        segments: list[TranscriptSegment],
        mode: str | None = None,
        instructions: str | None = None,
    ) -> list[TranscriptSegment]:
        """Refine segments via engine if it supports segment refinement."""
        engine = self._ensure_engine()
        if hasattr(engine, "refine_segments"):
            result: list[TranscriptSegment] = engine.refine_segments(segments, mode, instructions)
            return result

        # Fallback: use text-based refinement and assign to all segments
        combined_text = " ".join(seg.raw_text.strip() for seg in segments if seg.raw_text.strip())
        if not combined_text or not hasattr(engine, "refine_text"):
            return segments

        refined_text = self.refine_text(combined_text, instructions)
        return [replace(seg, refined_text=refined_text) for seg in segments]

    def transcribe_batch(self, audio_paths: list[Path]) -> list[list[TranscriptSegment]]:
        """Transcribe multiple audio files in a single batched call if supported.

        Falls back to sequential transcription if the engine doesn't support batching.
        Automatically uses the daemon server if it's running for faster inference.
        """
        # Try daemon first for fastest inference (model already in GPU memory)
        if self._check_daemon():
            try:
                from vociferous.server import batch_transcribe_via_daemon
                daemon_segments = batch_transcribe_via_daemon(
                    [Path(p) for p in audio_paths],
                    language=self.profile.options.language,
                )
                if daemon_segments is not None:
                    self._used_daemon = True
                    result: list[list[TranscriptSegment]] = daemon_segments
                    return result
            except Exception:
                pass  # Daemon failed, fallback to local engine

        # Fallback to local engine
        engine = self._ensure_engine()
        if hasattr(engine, "transcribe_files_batch"):
            batch_result: list[list[TranscriptSegment]] = engine.transcribe_files_batch(
                [Path(p) for p in audio_paths],
                self.profile.options
            )
            return batch_result
        # Fallback: sequential transcription
        return [self.transcribe(path) for path in audio_paths]





def transcribe_file_workflow(
    source: Source,
    engine_profile: EngineProfile,
    segmentation_profile: SegmentationProfile,
    *,
    refine: bool = True,
    refine_instructions: str | None = None,
    keep_intermediates: bool | None = None,
    artifact_config: ArtifactConfig | None = None,
    intermediate_dir: Path | None = None,
    condensed_path: Path | None = None,
    engine_worker: EngineWorker | None = None,
    use_daemon: bool = False,
    daemon_mode: str = "auto",
    preprocess: str | None = None,
    progress: TranscriptionProgress | None = None,
) -> TranscriptionResult:
    """Canonical decode → preprocess → VAD → condense → transcribe workflow.

    The workflow is file-first: all sources resolve to a local path, audio
    preprocessing happens in the audio module, and a single engine instance
    is reused via EngineWorker to keep the seam ready for out-of-process
    workers later.
    
    Args:
        source: Audio source to transcribe
        engine_profile: Engine configuration profile
        segmentation_profile: VAD and chunking settings
        refine: Whether to refine the transcript
        refine_instructions: Custom refinement instructions
        keep_intermediates: Keep intermediate files
        artifact_config: Artifact handling configuration
        intermediate_dir: Directory for intermediate files
        condensed_path: Pre-condensed audio path (skip VAD)
        engine_worker: Pre-configured engine worker
        use_daemon: Use warm model daemon if available (legacy, use daemon_mode)
        daemon_mode: Daemon mode - "never", "auto" (use if running), "always" (auto-start)
        preprocess: Audio preprocessing preset (none, basic, clean, phone, podcast)
        progress: Optional progress tracker for UI feedback
    """
    artifact_cfg = artifact_config or ArtifactConfig()
    # CLI override wins; otherwise follow config cleanup flag
    should_cleanup = (
        not keep_intermediates
        if keep_intermediates is not None
        else artifact_cfg.cleanup_intermediates
    )

    work_dir = Path(intermediate_dir or artifact_cfg.output_directory).expanduser()
    work_dir.mkdir(parents=True, exist_ok=True)

    cleanup_paths: list[Path] = []
    had_error = False
    worker = engine_worker or EngineWorker(
        engine_profile,
        use_daemon=use_daemon,
        daemon_mode=daemon_mode,
        progress=progress,
    )
    warnings: list[str] = list(worker.warnings)
    try:
        target_audio = source.resolve_to_path(work_dir)

        if condensed_path is None:
            def _name(step: str, ext: str) -> Path:
                return work_dir / artifact_cfg.naming_pattern.format(
                    input_name=target_audio.name,
                    input_stem=target_audio.stem,
                    step=step,
                    ext=ext,
                )

            decoded_path = _name("decoded", "wav")
            timestamps_path = _name("decoded_vad_timestamps", "json")

            # Step 1: Decode
            decode_task = progress.start_decode() if progress else None
            decoded_path = DecoderComponent().decode_to_wav(target_audio, decoded_path)
            if progress:
                progress.complete_decode(decode_task)
            
            # Step 1.5: Preprocess (if requested)
            if preprocess and preprocess != "none":
                from vociferous.audio.preprocessing import AudioPreprocessor, PreprocessingConfig
                
                preprocess_task = progress.start_preprocess() if progress else None
                preprocess_config = PreprocessingConfig.from_preset(preprocess)
                preprocessor = AudioPreprocessor(preprocess_config)
                
                preprocessed_path = _name("preprocessed", "wav")
                decoded_path = preprocessor.preprocess(decoded_path, preprocessed_path, progress=None)
                
                if progress:
                    progress.complete_preprocess(preprocess_task, preprocess)
                
                cleanup_paths.append(preprocessed_path)
            
            # Step 2: VAD
            vad_task = progress.start_vad() if progress else None
            timestamps = VADComponent(sample_rate=segmentation_profile.sample_rate, device=segmentation_profile.device).detect(
                decoded_path,
                output_path=timestamps_path,
                threshold=segmentation_profile.threshold,
                min_silence_ms=segmentation_profile.min_silence_ms,
                min_speech_ms=segmentation_profile.min_speech_ms,
                speech_pad_ms=segmentation_profile.speech_pad_ms,
                max_speech_duration_s=segmentation_profile.max_speech_duration_s,
            )
            if not timestamps:
                raise ValueError("No speech detected during VAD; aborting transcription.")
            if progress:
                progress.complete_vad(vad_task, len(timestamps))

            # Step 3: Condense
            condense_task = progress.start_condense() if progress else None
            condensed_files = CondenserComponent().condense(
                timestamps_path,
                decoded_path,
                output_path=None,  # Allow multiple chunks via profile-driven splitting
                segmentation_profile=segmentation_profile,
            )
            condensed_paths = condensed_files
            if progress:
                progress.complete_condense(condense_task, len(condensed_paths))

            if should_cleanup:
                cleanup_paths.extend([decoded_path, timestamps_path, *condensed_paths])
        else:
            condensed_paths = [Path(condensed_path)]

        # Get durations for offset calculation
        chunk_durations = [_wav_duration(p) for p in condensed_paths]
        
        # Step 4: Transcribe chunks
        transcribe_task = progress.start_transcribe(len(condensed_paths)) if progress else None
        
        # Use batch transcription for significant speedup (single inference call for all chunks)
        all_chunk_segments = worker.transcribe_batch(condensed_paths)
        
        if progress:
            progress.complete_transcribe(transcribe_task)
        
        # Apply time offsets to each chunk's segments
        all_segments: list[TranscriptSegment] = []
        offset = 0.0
        for chunk_segments, duration in zip(all_chunk_segments, chunk_durations):
            all_segments.extend(_offset_segments(chunk_segments, offset))
            offset += duration

        text = _segments_to_text(all_segments)

        # Step 5: Refinement
        if refine:
            refine_task = progress.start_refine() if progress else None
            try:
                text = worker.refine_text(text, refine_instructions)
                if progress:
                    progress.complete_refine(refine_task)
            except Exception as exc:  # pragma: no cover - safeguard
                warnings.append(f"Refinement failed: {exc}")
                if progress:
                    progress.warning(f"Refinement failed: {exc}")

        if progress:
            progress.success("Transcription complete")

        metadata = worker.metadata
        return TranscriptionResult(
            text=text,
            segments=tuple(all_segments),
            model_name=metadata.model_name,
            device=metadata.device,
            precision=metadata.precision,
            engine=engine_profile.kind,
            duration_s=all_segments[-1].end_s if all_segments else 0.0,
            warnings=tuple(warnings),
        )
    except Exception:
        had_error = True
        raise
    finally:
        if should_cleanup and (not had_error or not artifact_cfg.keep_on_error):
            for path in cleanup_paths:
                with suppress(OSError):
                    path.unlink(missing_ok=True)
            # Only remove the work directory if it was a temp dir we created
            if not intermediate_dir and artifact_cfg.output_directory == work_dir:
                with suppress(OSError):
                    work_dir.rmdir()


def transcribe_workflow(
    audio_path: Path,
    *,
    engine_kind: EngineKind,
    engine_config: EngineConfig,
    options: TranscriptionOptions,
    keep_intermediates: bool | None = None,
    artifact_config: ArtifactConfig | None = None,
    intermediate_dir: Path | None = None,
    condensed_path: Path | None = None,
    refine: bool = False,
    refine_instructions: str | None = None,
    engine: TranscriptionEngine | None = None,
    use_daemon: bool = False,
) -> TranscriptionResult:
    """Backward-compatible wrapper around the canonical workflow.

    Accepts the legacy parameter set used by CLI/GUI and forwards to
    `transcribe_file_workflow` with default segmentation settings.
    """

    engine_profile = EngineProfile(engine_kind, engine_config, options)
    segmentation_profile = SegmentationProfile()
    source: Source = FileSource(audio_path)

    worker = EngineWorker(engine_profile, engine=engine, use_daemon=use_daemon) if engine is not None else None

    return transcribe_file_workflow(
        source,
        engine_profile,
        segmentation_profile,
        refine=refine,
        refine_instructions=refine_instructions,
        keep_intermediates=keep_intermediates,
        artifact_config=artifact_config,
        intermediate_dir=intermediate_dir,
        condensed_path=condensed_path,
        engine_worker=worker,
        use_daemon=use_daemon,
    )
                
