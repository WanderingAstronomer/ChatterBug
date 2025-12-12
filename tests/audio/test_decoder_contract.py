"""Decoder contract tests using real audio input."""

from __future__ import annotations

import shutil
import subprocess
import sys
import wave
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        shutil.which("ffmpeg") is None,
        reason="ffmpeg is required for decoder contract tests",
    ),
]

SAMPLES_DIR = Path(__file__).resolve().parent / "sample_audio"
SHORT_FLAC = SAMPLES_DIR / "ASR_Test.flac"
ARTIFACTS_DIR = Path(__file__).parent / "artifacts"

if not SHORT_FLAC.exists():
    pytest.skip("Sample audio fixture missing", allow_module_level=True)


@pytest.fixture(autouse=True)
def ensure_artifacts_dir() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "vociferous.cli.main", *args],
        cwd=ARTIFACTS_DIR,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_decoder_standardizes_flac_to_pcm_wav() -> None:
    """Decoder converts FLAC to PCM mono 16kHz WAV."""
    input_file = SHORT_FLAC
    output_file = ARTIFACTS_DIR / "ASR_Test_decoded.wav"

    result = _run_cli(["decode", str(input_file), "--output", str(output_file)])

    assert result.returncode == 0, f"Decode failed: {result.stderr}"
    assert output_file.exists(), "Decoded output missing"

    with wave.open(str(output_file), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getframerate() == 16000
        assert wav.getsampwidth() == 2


def test_decoder_errors_on_invalid_file() -> None:
    """Decoder returns non-zero on invalid input."""
    invalid_file = ARTIFACTS_DIR / "not_audio.txt"
    invalid_file.write_text("This is not audio")

    result = _run_cli(["decode", str(invalid_file)])

    assert result.returncode != 0
    assert "error" in result.stderr.lower() or "failed" in result.stderr.lower()
