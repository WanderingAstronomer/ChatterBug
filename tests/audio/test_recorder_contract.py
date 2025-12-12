"""Recorder contract test (interactive CLI).

Skipped automatically in CI or when sounddevice is unavailable.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import wave
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
]

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"


@pytest.fixture(autouse=True)
def ensure_artifacts_dir() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def _sounddevice_available() -> bool:
    try:
        import sounddevice  # noqa: F401
    except Exception:
        return False
    return True


skip_condition = False
skip_reason = ""
if os.getenv("CI") == "true":
    skip_condition = True
    skip_reason = "Recorder test skipped in CI (no audio device)"
elif not _sounddevice_available():
    skip_condition = True
    skip_reason = "Recorder test skipped: sounddevice not installed"


@pytest.mark.skipif(skip_condition, reason=skip_reason or "Recorder test requires interactive audio device")
def test_recorder_captures_audio() -> None:
    """Recorder captures a short WAV clip via CLI."""
    output_path = ARTIFACTS_DIR / "test_recording.wav"

    proc = subprocess.Popen(
        [sys.executable, "-m", "vociferous.cli.main", "record", "--output", str(output_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        # Start recording
        time.sleep(0.5)
        assert proc.stdin is not None
        proc.stdin.write("\n")
        proc.stdin.flush()

        # Capture ~1.5 seconds of audio
        time.sleep(1.5)

        # Stop recording
        proc.stdin.write("\n")
        proc.stdin.flush()

        proc.wait(timeout=15)
    finally:
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    assert proc.returncode == 0, f"Recorder failed: {proc.stderr.read() if proc.stderr else ''}"
    assert output_path.exists(), "Recording not created"

    with wave.open(str(output_path), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == 16000
        assert wf.getsampwidth() == 2
        duration_s = wf.getnframes() / float(wf.getframerate())
        assert duration_s > 0.5, f"Recording too short ({duration_s:.2f}s)"
