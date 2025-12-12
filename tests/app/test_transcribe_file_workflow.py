"""Integration-style test for the canonical transcribe_file_workflow."""

from __future__ import annotations

import shutil
import wave
from pathlib import Path

import pytest

from vociferous.app.workflow import EngineWorker, transcribe_file_workflow
from vociferous.config.schema import ArtifactConfig
from vociferous.domain.model import (
    EngineConfig,
    EngineMetadata,
    EngineProfile,
    SegmentationProfile,
    TranscriptionEngine,
    TranscriptionOptions,
    TranscriptSegment,
)
from vociferous.sources import FileSource

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "audio" / "sample_audio"
SHORT_FLAC = SAMPLES_DIR / "ASR_Test.flac"

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg is required for workflow contract tests"
)

if not SHORT_FLAC.exists():
    pytest.skip("Sample audio fixture missing", allow_module_level=True)


def _duration_seconds(audio_path: Path) -> float:
    with wave.open(str(audio_path), "rb") as wf:
        return wf.getnframes() / wf.getframerate()


class DummyEngine(TranscriptionEngine):
    """Lightweight engine for workflow wiring tests."""

    def __init__(self) -> None:
        self.config = EngineConfig(model_name="dummy")
        self.model_name = "dummy"

    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(model_name="dummy", device="cpu", precision="float32")

    def transcribe_file(self, audio_path: Path, options: TranscriptionOptions | None = None) -> list[TranscriptSegment]:
        return [
            TranscriptSegment(
                id="seg-0",
                start=0.0,
                end=_duration_seconds(audio_path),
                raw_text="dummy transcript",
            )
        ]


def test_transcribe_file_workflow_end_to_end(tmp_path: Path) -> None:
    source = FileSource(SHORT_FLAC)
    engine_profile = EngineProfile(
        "whisper_turbo",
        EngineConfig(model_name="dummy"),
        TranscriptionOptions(),
    )
    segmentation_profile = SegmentationProfile()
    worker = EngineWorker(engine_profile, engine=DummyEngine())

    result = transcribe_file_workflow(
        source,
        engine_profile,
        segmentation_profile,
        refine=False,
        artifact_config=ArtifactConfig(output_directory=tmp_path),
        engine_worker=worker,
    )

    assert result.segments, "Workflow should produce transcript segments"
    assert result.text.strip(), "Workflow should surface transcript text"
    assert result.model_name == "dummy"
