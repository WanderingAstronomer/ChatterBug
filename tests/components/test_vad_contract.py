"""VAD contract tests using real audio and CLI."""

from __future__ import annotations

import json
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


def _decode_sample(tmp_path: Path) -> Path:
    decoded = tmp_path / "ASR_Test_decoded.wav"
    result = _run_cli(
        ["decode", str(SAMPLES_DIR / "ASR_Test.flac"), "--output", str(decoded)],
        tmp_path,
    )
    assert result.returncode == 0, f"Decode failed: {result.stderr}"
    assert decoded.exists()
    return decoded


def test_vad_produces_timestamps(tmp_path: Path) -> None:
    """VAD detects speech and emits JSON timestamps."""
    decoded = _decode_sample(tmp_path)

    result = _run_cli(["vad", str(decoded)], tmp_path)
    assert result.returncode == 0, f"VAD failed: {result.stderr}"

    output_file = decoded.with_name(f"{decoded.stem}_vad_timestamps.json")
    assert output_file.exists(), "Timestamps file not created"

    with open(output_file) as f:
        timestamps = json.load(f)

    assert isinstance(timestamps, list)
    assert len(timestamps) > 0
    for ts in timestamps:
        assert "start" in ts and "end" in ts
        assert ts["end"] > ts["start"]


def test_vad_returns_empty_for_silence(tmp_path: Path) -> None:
    """VAD returns empty list on pure silence input."""
    silence_path = tmp_path / "silence.wav"
    with wave.open(str(silence_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 16000 * 5)  # 5 seconds of silence

    result = _run_cli(
        ["vad", str(silence_path), "--threshold", "0.8", "--min-speech-ms", "250"],
        tmp_path,
    )
    assert result.returncode == 0, f"VAD failed on silence: {result.stderr}"

    output_file = silence_path.with_name(f"{silence_path.stem}_vad_timestamps.json")
    with open(output_file) as f:
        timestamps = json.load(f)

    assert timestamps == []


def test_vad_respects_custom_output(tmp_path: Path) -> None:
    """VAD saves timestamps to custom path when requested."""
    decoded = _decode_sample(tmp_path)
    custom_output = tmp_path / "custom_timestamps.json"

    result = _run_cli(
        ["vad", str(decoded), "--output", str(custom_output)],
        tmp_path,
    )
    assert result.returncode == 0, f"VAD failed: {result.stderr}"
    assert custom_output.exists()

    with open(custom_output) as f:
        timestamps = json.load(f)
    assert len(timestamps) > 0
