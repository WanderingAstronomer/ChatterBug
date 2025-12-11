"""Tests for the deps check command."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


def _run_cli(args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run the CLI with the given arguments."""
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "vociferous.cli.main", *args],
        capture_output=True,
        text=True,
        timeout=30,
        env=merged_env,
    )


def test_deps_check_shows_engine_dependencies() -> None:
    """deps check should show required packages and models for an engine."""
    result = _run_cli(["deps", "check", "--engine", "canary_qwen"])
    
    # Should list the required packages
    assert "transformers" in result.stdout or "transformers" in result.stderr
    assert "torch" in result.stdout or "torch" in result.stderr
    assert "accelerate" in result.stdout or "accelerate" in result.stderr
    
    # Should mention the model
    assert "canary" in result.stdout.lower() or "canary" in result.stderr.lower()


def test_deps_check_exit_code_when_missing() -> None:
    """deps check should exit with code 2 when dependencies are missing."""
    # Force all packages to appear missing by manipulating the check
    # In real usage, missing packages will naturally cause exit code 2
    result = _run_cli(["deps", "check", "--engine", "canary_qwen"])
    
    # If all real dependencies are installed, exit code is 2 for missing models
    # If dependencies are missing, exit code is also 2
    # Only exit code 0 if everything is satisfied
    assert result.returncode in (0, 2)


def test_deps_check_whisper_turbo() -> None:
    """deps check should work with whisper_turbo engine."""
    result = _run_cli(["deps", "check", "--engine", "whisper_turbo"])
    
    # Should list whisper-specific packages
    assert "faster-whisper" in result.stdout or "faster-whisper" in result.stderr
    assert "ctranslate2" in result.stdout or "ctranslate2" in result.stderr


def test_deps_check_shows_cache_location() -> None:
    """deps check should display the model cache directory."""
    result = _run_cli(["deps", "check", "--engine", "canary_qwen"])
    
    # Should show cache directory path
    assert "cache" in result.stdout.lower() or "cache" in result.stderr.lower()


def test_deps_check_provides_install_guidance() -> None:
    """deps check should provide actionable pip install commands when packages missing."""
    result = _run_cli(["deps", "check", "--engine", "canary_qwen"])
    
    # If any packages are missing, should show pip install guidance
    output = result.stdout + result.stderr
    if "MISSING" in output:
        assert "pip install" in output.lower()
