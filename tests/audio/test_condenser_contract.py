"""Condenser contract tests using real VAD timestamps."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        shutil.which("ffmpeg") is None,
        reason="ffmpeg is required for condenser contract tests",
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
        timeout=60,
    )


def _decode_and_vad() -> tuple[Path, Path]:
    decoded = ARTIFACTS_DIR / "ASR_Test_decoded.wav"
    timestamps = ARTIFACTS_DIR / "ASR_Test_decoded_vad_timestamps.json"

    dec = _run_cli(
        ["decode", str(SHORT_FLAC), "--output", str(decoded)],
    )
    assert dec.returncode == 0, f"Decode failed: {dec.stderr}"

    vad = _run_cli(["vad", str(decoded), "--output", str(timestamps)])
    assert vad.returncode == 0, f"VAD failed: {vad.stderr}"

    return decoded, timestamps


def test_condenser_creates_smaller_file() -> None:
    """Condense removes silence and yields a smaller WAV."""
    decoded, timestamps = _decode_and_vad()
    decoded_size = decoded.stat().st_size

    result = _run_cli(["condense", str(timestamps), str(decoded)])
    assert result.returncode == 0, f"Condense failed: {result.stderr}"

    output_file = ARTIFACTS_DIR / f"{decoded.stem}_condensed.wav"
    assert output_file.exists(), "Condensed output missing"
    assert output_file.stat().st_size < decoded_size


def test_condenser_requires_timestamps_file() -> None:
    """Condense should fail when timestamps file is missing."""
    decoded = ARTIFACTS_DIR / "missing_decoded.wav"
    decoded.write_bytes(b"")  # placeholder; command will error before decoding
    missing = ARTIFACTS_DIR / "missing_timestamps.json"

    result = _run_cli(["condense", str(missing), str(decoded)])

    assert result.returncode != 0
