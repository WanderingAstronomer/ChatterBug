"""VAD contract tests using real audio and CLI."""

from __future__ import annotations

import json
import os
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
        reason="ffmpeg is required for VAD contract tests",
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


def _run_cli(args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "vociferous.cli.main", *args],
        cwd=ARTIFACTS_DIR,
        capture_output=True,
        text=True,
        timeout=30,
        env=merged_env,
    )


def _decode_sample() -> Path:
    decoded = ARTIFACTS_DIR / "ASR_Test_decoded.wav"
    result = _run_cli(
        ["decode", str(SHORT_FLAC), "--output", str(decoded)],
    )
    assert result.returncode == 0, f"Decode failed: {result.stderr}"
    assert decoded.exists()
    return decoded


def test_vad_produces_timestamps() -> None:
    """VAD detects speech and emits JSON timestamps."""
    decoded = _decode_sample()

    result = _run_cli(["vad", str(decoded)])
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


def test_vad_returns_empty_for_silence() -> None:
    """VAD returns empty list on pure silence input."""
    silence_path = ARTIFACTS_DIR / "silence.wav"
    with wave.open(str(silence_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 16000 * 5)  # 5 seconds of silence

    result = _run_cli(
        ["vad", str(silence_path), "--threshold", "0.8", "--min-speech-ms", "250"],
    )
    assert result.returncode == 0, f"VAD failed on silence: {result.stderr}"

    output_file = silence_path.with_name(f"{silence_path.stem}_vad_timestamps.json")
    with open(output_file) as f:
        timestamps = json.load(f)

    assert timestamps == []


def test_vad_respects_custom_output() -> None:
    """VAD saves timestamps to custom path when requested."""
    decoded = _decode_sample()
    custom_output = ARTIFACTS_DIR / "custom_timestamps.json"

    result = _run_cli(
        ["vad", str(decoded), "--output", str(custom_output)],
    )
    assert result.returncode == 0, f"VAD failed: {result.stderr}"
    assert custom_output.exists()

    with open(custom_output) as f:
        timestamps = json.load(f)
    assert len(timestamps) > 0


def test_vad_missing_ffmpeg_shows_guidance() -> None:
    """VAD exits with rich error panel when ffmpeg is absent."""
    decoded = _decode_sample()

    env = {"PATH": ""}
    result = _run_cli(["vad", str(decoded)], env=env)

    # DependencyError is caught by main() and converted to exit code 1
    assert result.returncode == 1
    # Rich error panel with guidance is shown in stdout
    assert "FFmpeg is not installed" in result.stdout
    assert "Install FFmpeg" in result.stdout
