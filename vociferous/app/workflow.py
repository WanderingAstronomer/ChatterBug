from __future__ import annotations

"""Batch transcription workflows (no sessions, no arbiters)."""

import wave
from dataclasses import replace
from pathlib import Path
from typing import Iterable, Sequence

from vociferous.cli.components.condenser import CondenserComponent
from vociferous.cli.components.decoder import DecoderComponent
from vociferous.cli.components.vad import VADComponent
from vociferous.config.schema import ArtifactConfig
from vociferous.domain.model import (
    EngineProfile,
    EngineConfig,
    EngineKind,
    SegmentationProfile,
    TranscriptSegment,
    TranscriptionOptions,
    TranscriptionResult,
    TranscriptionEngine,
)
from vociferous.engines.factory import build_engine
from vociferous.sources import FileSource, Source


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
    loaded if the daemon is not running.
    """

    def __init__(
        self,
        profile: EngineProfile,
        *,
        engine: TranscriptionEngine | None = None,
        use_daemon: bool = True,
    ) -> None:
        self.profile = profile
        self._provided_engine = engine
        self._engine: TranscriptionEngine | None = engine
        self._warnings: list[str] = []
        self._use_daemon = use_daemon
        self._daemon_checked = False
        self._daemon_available = False
        self._used_daemon = False  # Track if daemon was actually used
        
        # Only load engine immediately if one was provided
        # Otherwise, defer to first use to allow daemon check
        if engine is not None:
            self._engine = engine

    def _check_daemon(self) -> bool:
        """Check if daemon is available (cached)."""
        if self._daemon_checked:
            return self._daemon_available
        
        self._daemon_checked = True
        if not self._use_daemon:
            self._daemon_available = False
            return False
            
        try:
            from vociferous.server import is_daemon_running
            self._daemon_available = is_daemon_running()
        except ImportError:
            self._daemon_available = False
        
        return self._daemon_available

    def _ensure_engine(self) -> TranscriptionEngine:
        """Lazily load the engine if needed."""
        if self._engine is None:
            self._engine = build_engine(self.profile.kind, self.profile.config)
        return self._engine

    @property
    def metadata(self):
        """Get engine metadata.
        
        If daemon was used, returns metadata based on profile config.
        Otherwise, loads the engine and gets its metadata.
        """
        if self._used_daemon:
            # Return metadata based on what we know from config
            from vociferous.domain.model import EngineMetadata
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
        return self._ensure_engine().transcribe_file(Path(audio_path), self.profile.options)

    def refine_text(self, text: str, instructions: str | None = None) -> str:
        engine = self._ensure_engine()
        if hasattr(engine, "refine_text"):
            return engine.refine_text(text, instructions)  # type: ignore[attr-defined]
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
            return engine.refine_segments(segments, mode, instructions)  # type: ignore[attr-defined]
        
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
                from vociferous.server import transcribe_via_daemon
                daemon_segments = transcribe_via_daemon(
                    [Path(p) for p in audio_paths],
                    language=self.profile.options.language,
                )
                if daemon_segments is not None:
                    self._used_daemon = True  # Mark that daemon was used
                    # Daemon returns flat list, need to group by audio file
                    # For now, return all segments as a single group since daemon 
                    # already handles batching internally
                    return [daemon_segments]
            except Exception:
                pass  # Daemon failed, fallback to local engine
        
        # Fallback to local engine
        engine = self._ensure_engine()
        if hasattr(engine, "transcribe_files_batch"):
            return engine.transcribe_files_batch(  # type: ignore[attr-defined]
                [Path(p) for p in audio_paths], 
                self.profile.options
            )
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
) -> TranscriptionResult:
    """Canonical decode → VAD → condense → transcribe workflow.

    The workflow is file-first: all sources resolve to a local path, audio
    preprocessing happens in the audio module, and a single engine instance
    is reused via EngineWorker to keep the seam ready for out-of-process
    workers later.
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
    worker = engine_worker or EngineWorker(engine_profile)
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
            condensed_target = _name("decoded_condensed", "wav")

            decoded_path = DecoderComponent().decode_to_wav(target_audio, decoded_path)
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

            condensed_files = CondenserComponent().condense(
                timestamps_path,
                decoded_path,
                output_path=None,  # Allow multiple chunks via profile-driven splitting
                segmentation_profile=segmentation_profile,
            )
            condensed_paths = condensed_files

            if should_cleanup:
                cleanup_paths.extend([decoded_path, timestamps_path, *condensed_paths])
        else:
            condensed_paths = [Path(condensed_path)]

        # Get durations for offset calculation
        chunk_durations = [_wav_duration(p) for p in condensed_paths]
        
        # Use batch transcription for significant speedup (single inference call for all chunks)
        all_chunk_segments = worker.transcribe_batch(condensed_paths)
        
        # Apply time offsets to each chunk's segments
        all_segments: list[TranscriptSegment] = []
        offset = 0.0
        for chunk_segments, duration in zip(all_chunk_segments, chunk_durations):
            all_segments.extend(_offset_segments(chunk_segments, offset))
            offset += duration

        text = _segments_to_text(all_segments)

        if refine:
            try:
                text = worker.refine_text(text, refine_instructions)
            except Exception as exc:  # pragma: no cover - safeguard
                warnings.append(f"Refinement failed: {exc}")

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
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
            # Only remove the work directory if it was a temp dir we created
            if not intermediate_dir and artifact_cfg.output_directory == work_dir:
                try:
                    work_dir.rmdir()
                except OSError:
                    pass


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
    engine=None,
) -> TranscriptionResult:
    """Backward-compatible wrapper around the canonical workflow.

    Accepts the legacy parameter set used by CLI/GUI and forwards to
    `transcribe_file_workflow` with default segmentation settings.
    """

    engine_profile = EngineProfile(engine_kind, engine_config, options)
    segmentation_profile = SegmentationProfile()
    source: Source = FileSource(audio_path)

    worker = EngineWorker(engine_profile, engine=engine) if engine is not None else None

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
    )
                