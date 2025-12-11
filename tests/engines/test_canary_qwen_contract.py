"""Contract tests for CanaryQwenEngine with real model loading.

NOTE: These tests require CUDA GPU with sufficient VRAM (~3GB free minimum).
They load the actual Canary-Qwen 2.5B model which is memory-intensive.
Tests will be skipped if GPU memory is insufficient.
"""

from __future__ import annotations

from pathlib import Path

import pytest

torch = pytest.importorskip("torch", reason="Canary tests require PyTorch")
pytest.importorskip(
    "nemo.collections.speechlm2.models",
    reason="Canary-Qwen tests require NeMo dependencies",
)
if not torch.cuda.is_available():  # pragma: no cover - hardware guard
    pytest.skip("Canary tests require CUDA GPU", allow_module_level=True)

from vociferous.domain.model import EngineConfig, TranscriptionOptions
from vociferous.engines.canary_qwen import CanaryQwenEngine

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "audio" / "sample_audio"
SAMPLE_WAV = SAMPLES_DIR / "ASR_Test_preprocessed.wav"  # Preprocessed: decoded → VAD → condensed
ARTIFACTS_DIR = Path(__file__).parent / "artifacts"

# Skip all Canary tests if insufficient GPU memory
# pytestmark = pytest.mark.skip(reason="Canary tests require GPU with ~3GB+ free VRAM. Run manually on GPU systems with sufficient memory.")


@pytest.fixture(autouse=True)
def ensure_artifacts_dir() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def canary_engine() -> CanaryQwenEngine:
    config = EngineConfig(
        model_name="nvidia/canary-qwen-2.5b",
        device="cuda",  # Canary requires CUDA
        compute_type="float16",
    )
    return CanaryQwenEngine(config)


def test_canary_asr_mode(canary_engine: CanaryQwenEngine) -> None:
    options = TranscriptionOptions(language="en")

    segments = canary_engine.transcribe_file(SAMPLE_WAV, options)

    assert segments, "No segments produced"
    for seg in segments:
        assert seg.text.strip()
        assert seg.end_s >= seg.start_s

    # Persist transcript for inspection
    transcript_path = ARTIFACTS_DIR / "canary_asr_transcript.txt"
    transcript_path.write_text(" ".join(seg.text for seg in segments))


def test_canary_refine_mode(canary_engine: CanaryQwenEngine) -> None:
    raw_text = "uh so like i was thinking um we should maybe do that"

    refined = canary_engine.refine_text(raw_text)

    assert refined.strip(), "Refined text is empty"
    assert refined != raw_text, "Text not refined"


def test_canary_dual_pass_integration(canary_engine: CanaryQwenEngine) -> None:
    options = TranscriptionOptions(language="en")

    segments = canary_engine.transcribe_file(SAMPLE_WAV, options)
    raw_text = " ".join(seg.text for seg in segments)
    assert raw_text.strip(), "ASR produced no text"

    refined = canary_engine.refine_text(raw_text)
    assert refined.strip(), "Refinement produced no text"

    artifact = ARTIFACTS_DIR / "canary_dual_pass.txt"
    artifact.write_text(refined)


def test_canary_metadata(canary_engine: CanaryQwenEngine) -> None:
    meta = canary_engine.metadata

    assert "canary" in meta.model_name.lower()
    assert meta.device == "cuda"  # Canary requires CUDA
