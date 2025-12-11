from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg is required for dependency checks"
)


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


def test_check_warns_but_succeeds_without_sounddevice() -> None:
    """Missing sounddevice should warn and still exit success when ffmpeg is present."""
    env = {"VOCIFEROUS_FORCE_MISSING_SOUNDDEVICE": "1"}
    result = _run_cli(["check"], env=env)

    assert result.returncode == 0
    assert "sounddevice" in result.stdout
    assert "WARN" in result.stdout
    assert "mic capture disabled" in result.stdout
