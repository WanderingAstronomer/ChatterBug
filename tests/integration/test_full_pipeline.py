"""End-to-end pipeline: decode -> vad -> condense."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        shutil.which("ffmpeg") is None,
        reason="ffmpeg is required for pipeline contract tests",
    ),
]

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "audio" / "sample_audio"
SHORT_FLAC = SAMPLES_DIR / "ASR_Test.flac"

if not SHORT_FLAC.exists():
    pytest.skip("Sample audio fixture missing", allow_module_level=True)


def _run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "vociferous.cli.main", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_decode_vad_condense_chain(tmp_path: Path) -> None:
    """Full chain produces timestamps and condensed audio."""
    input_file = SHORT_FLAC

    decoded = tmp_path / "ASR_Test_decoded.wav"
    timestamps = tmp_path / "ASR_Test_decoded_vad_timestamps.json"
    condensed = tmp_path / "ASR_Test_decoded_condensed.wav"

    dec = _run_cli(["decode", str(input_file), "--output", str(decoded)], tmp_path)
    assert dec.returncode == 0, f"Decode failed: {dec.stderr}"
    assert decoded.exists()

    vad = _run_cli(["vad", str(decoded), "--output", str(timestamps)], tmp_path)
    assert vad.returncode == 0, f"VAD failed: {vad.stderr}"
    assert timestamps.exists()

    with open(timestamps) as f:
        spans = json.load(f)
    assert spans, "No speech segments detected"

    cond = _run_cli(["condense", str(timestamps), str(decoded), "--output", str(condensed)], tmp_path)
    assert cond.returncode == 0, f"Condense failed: {cond.stderr}"
    
    # Condenser may produce a single file OR multiple chunks (part_001, part_002, etc.)
    # Check for either output format
    chunk_files = list(tmp_path.glob("*_condensed_part_*.wav"))
    if condensed.exists():
        # Single chunk output
        assert condensed.stat().st_size < decoded.stat().st_size
    else:
        # Multiple chunk output - verify at least one chunk exists
        assert chunk_files, f"No condensed output found: {list(tmp_path.glob('*.wav'))}"
        total_size = sum(f.stat().st_size for f in chunk_files)
        assert total_size < decoded.stat().st_size
