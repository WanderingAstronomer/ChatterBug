"""Condenser contract tests using real VAD timestamps."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "samples"


def _run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "vociferous.cli.main", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _decode_and_vad(tmp_path: Path) -> tuple[Path, Path]:
    decoded = tmp_path / "ASR_Test_decoded.wav"
    timestamps = tmp_path / "ASR_Test_decoded_vad_timestamps.json"

    dec = _run_cli(
        ["decode", str(SAMPLES_DIR / "ASR_Test.flac"), "--output", str(decoded)],
        tmp_path,
    )
    assert dec.returncode == 0, f"Decode failed: {dec.stderr}"

    vad = _run_cli(["vad", str(decoded), "--output", str(timestamps)], tmp_path)
    assert vad.returncode == 0, f"VAD failed: {vad.stderr}"

    return decoded, timestamps


def test_condenser_creates_smaller_file(tmp_path: Path) -> None:
    """Condense removes silence and yields a smaller WAV."""
    decoded, timestamps = _decode_and_vad(tmp_path)
    decoded_size = decoded.stat().st_size

    result = _run_cli(["condense", str(timestamps), str(decoded)], tmp_path)
    assert result.returncode == 0, f"Condense failed: {result.stderr}"

    output_file = tmp_path / f"{decoded.stem}_condensed.wav"
    assert output_file.exists(), "Condensed output missing"
    assert output_file.stat().st_size < decoded_size


def test_condenser_requires_timestamps_file(tmp_path: Path) -> None:
    """Condense should fail when timestamps file is missing."""
    decoded = tmp_path / "missing_decoded.wav"
    decoded.write_bytes(b"")  # placeholder; command will error before decoding
    missing = tmp_path / "missing_timestamps.json"

    result = _run_cli(["condense", str(missing), str(decoded)], tmp_path)

    assert result.returncode != 0
