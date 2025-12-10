"""Decoder contract tests using real audio input."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import wave

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "samples"


def _run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "vociferous.cli.main", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_decoder_standardizes_flac_to_pcm_wav(tmp_path: Path) -> None:
    """Decoder converts FLAC to PCM mono 16kHz WAV."""
    input_file = SAMPLES_DIR / "ASR_Test.flac"
    output_file = tmp_path / "ASR_Test_decoded.wav"

    result = _run_cli(["decode", str(input_file), "--output", str(output_file)], tmp_path)

    assert result.returncode == 0, f"Decode failed: {result.stderr}"
    assert output_file.exists(), "Decoded output missing"

    with wave.open(str(output_file), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getframerate() == 16000
        assert wav.getsampwidth() == 2


def test_decoder_errors_on_invalid_file(tmp_path: Path) -> None:
    """Decoder returns non-zero on invalid input."""
    invalid_file = tmp_path / "not_audio.txt"
    invalid_file.write_text("This is not audio")

    result = _run_cli(["decode", str(invalid_file)], tmp_path)

    assert result.returncode != 0
    assert "error" in result.stderr.lower() or "failed" in result.stderr.lower()
