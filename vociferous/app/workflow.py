from __future__ import annotations

"""Batch transcription workflows (no sessions, no arbiters)."""

from pathlib import Path
from typing import Iterable, Sequence

from vociferous.cli.components import CondenserComponent, DecoderComponent, VADComponent
from vociferous.config.schema import ArtifactConfig
from vociferous.domain.model import (
    EngineConfig,
    EngineKind,
    TranscriptSegment,
    TranscriptionOptions,
    TranscriptionResult,
)
from vociferous.engines.factory import build_engine


def _ensure_engine(engine, engine_kind: EngineKind, engine_config: EngineConfig):
    """Return provided engine or build one from config."""
    if engine is not None:
        return engine
    return build_engine(engine_kind, engine_config)


def _segments_to_text(segments: Iterable[TranscriptSegment]) -> str:
    """Join segment text into a single transcript string."""
    return " ".join(seg.text.strip() for seg in segments).strip()


def transcribe_preprocessed(
    audio_path: Path,
    *,
    engine_kind: EngineKind,
    engine_config: EngineConfig,
    options: TranscriptionOptions,
    refine: bool = False,
    refine_instructions: str | None = None,
    engine=None,
) -> TranscriptionResult:
    """Transcribe a preprocessed (decoded + condensed) audio file.

    Optionally performs a second-pass text refinement if the engine exposes
    `refine_text` and `refine` is enabled.
    """
    engine_instance = _ensure_engine(engine, engine_kind, engine_config)

    warnings: list[str] = []
    if getattr(engine_instance, "use_mock", False):
        reason = getattr(engine_instance, "mock_reason", None)
        warnings.append(
            reason
            or "Engine is running in mock mode (install dependencies or set params.use_mock=true intentionally)."
        )

    segments: Sequence[TranscriptSegment] = tuple(engine_instance.transcribe_file(audio_path, options))
    text = _segments_to_text(segments)

    if refine and hasattr(engine_instance, "refine_text"):
        try:
            refined_text = engine_instance.refine_text(text, refine_instructions)  # type: ignore[attr-defined]
            text = refined_text
        except Exception as exc:  # pragma: no cover - safeguard
            warnings.append(f"Refinement failed: {exc}")

    metadata = engine_instance.metadata
    return TranscriptionResult(
        text=text,
        segments=segments,
        model_name=metadata.model_name,
        device=metadata.device,
        precision=metadata.precision,
        engine=engine_kind,
        duration_s=segments[-1].end_s if segments else 0.0,
        warnings=tuple(warnings),
    )


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
    """Decode → VAD → condense → transcribe pipeline using components.

    This replaces the TranscriptionSession/SegmentArbiter path with a
    transparent, file-based workflow suitable for debugging and CLI usage.
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
    try:
        target_audio = Path(audio_path)

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
            timestamps = VADComponent().detect(decoded_path, output_path=timestamps_path)
            if not timestamps:
                raise ValueError("No speech detected during VAD; aborting transcription.")

            condensed_files = CondenserComponent().condense(
                timestamps_path,
                decoded_path,
                output_path=condensed_target,
            )
            if len(condensed_files) != 1:
                raise ValueError("Condense produced multiple files; manual pipeline required for splits.")
            condensed_path = condensed_files[0]

            if should_cleanup:
                cleanup_paths.extend([decoded_path, timestamps_path, condensed_path])
        else:
            condensed_path = Path(condensed_path)

        result = transcribe_preprocessed(
            condensed_path,
            engine_kind=engine_kind,
            engine_config=engine_config,
            options=options,
            refine=refine,
            refine_instructions=refine_instructions,
            engine=engine,
        )
        return result
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
                