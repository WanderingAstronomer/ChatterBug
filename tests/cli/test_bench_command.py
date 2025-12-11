"""Test bench command contract."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


SAMPLE_AUDIO_DIR = Path(__file__).parent.parent / "audio" / "sample_audio"
ARTIFACTS_DIR = Path(__file__).parent / "artifacts"


def _run_bench(corpus: Path, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    """Helper to run bench command via subprocess."""
    # Use sys.executable to get the current Python interpreter (handles venv)
    import sys
    cmd = [
        sys.executable,
        "-m",
        "vociferous.cli.main",
        "bench",
        str(corpus),
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )


@pytest.mark.skip(reason="Requires full engine initialization and model loading")
@pytest.mark.slow
def test_bench_single_file_corpus() -> None:
    """Bench command runs on single-file corpus and prints RTF metrics."""
    # Use existing sample audio as corpus
    result = _run_bench(SAMPLE_AUDIO_DIR, ["--pattern", "ASR_Test.flac"])
    
    assert result.returncode == 0, f"Bench failed: {result.stderr}"
    
    # Verify output contains expected metrics
    output = result.stdout
    assert "Benchmark Results" in output
    assert "Duration (s)" in output
    assert "Wall Time (s)" in output
    assert "RTF" in output
    assert "Aggregate Metrics" in output
    assert "Total Audio Duration" in output
    assert "Aggregate RTF" in output
    assert "Throughput" in output


@pytest.mark.slow
def test_bench_empty_corpus_fails() -> None:
    """Bench command fails gracefully on empty corpus."""
    empty_dir = ARTIFACTS_DIR / "empty_corpus"
    empty_dir.mkdir(exist_ok=True, parents=True)
    
    result = _run_bench(empty_dir)
    
    assert result.returncode == 2
    assert "No files matching pattern" in result.stderr


@pytest.mark.slow
def test_bench_nonexistent_corpus_fails() -> None:
    """Bench command fails gracefully when corpus doesn't exist."""
    nonexistent = ARTIFACTS_DIR / "does_not_exist"
    
    result = _run_bench(nonexistent)
    
    assert result.returncode == 2
    assert "not found" in result.stderr


@pytest.mark.skip(reason="Requires full engine initialization and model loading")
@pytest.mark.slow
def test_bench_with_custom_pattern() -> None:
    """Bench command accepts custom file pattern."""
    result = _run_bench(SAMPLE_AUDIO_DIR, ["--pattern", "*.flac"])
    
    assert result.returncode == 0, f"Bench failed: {result.stderr}"
    
    # Should process multiple files
    output = result.stdout
    assert "ASR_Test.flac" in output or "Recording" in output


@pytest.mark.slow
def test_bench_invalid_engine_profile_fails() -> None:
    """Bench command fails gracefully with invalid engine profile."""
    result = _run_bench(
        SAMPLE_AUDIO_DIR,
        ["--pattern", "ASR_Test.flac", "--engine-profile", "does_not_exist"],
    )
    
    assert result.returncode == 2
    # May fail on segmentation profile or engine profile depending on config
    assert ("not found" in result.stderr) or ("Available" in result.stderr)
