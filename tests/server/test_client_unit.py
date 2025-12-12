"""Tests for daemon HTTP client (unit tests, no mocks).

These tests verify:
1. Client initialization and configuration
2. Exception types and hierarchy
3. Helper functions that don't require network (PID file handling)

For tests that require a running daemon, see test_daemon_integration.py
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


class TestDaemonClientInitialization:
    """Test DaemonClient initialization (no network needed)."""

    def test_client_initialization_defaults(self) -> None:
        """Test DaemonClient initializes with correct defaults."""
        from vociferous.server.client import (
            DEFAULT_DAEMON_HOST,
            DEFAULT_DAEMON_PORT,
            DEFAULT_TIMEOUT_S,
            DaemonClient,
        )
        
        client = DaemonClient()
        assert client.base_url == f"http://{DEFAULT_DAEMON_HOST}:{DEFAULT_DAEMON_PORT}"
        assert client.timeout == DEFAULT_TIMEOUT_S

    def test_client_custom_config(self) -> None:
        """Test DaemonClient accepts custom configuration."""
        from vociferous.server.client import DaemonClient
        
        client = DaemonClient(host="localhost", port=9999, timeout=120.0)
        assert client.base_url == "http://localhost:9999"
        assert client.timeout == 120.0

    def test_client_default_values(self) -> None:
        """Test that default values are sensible."""
        from vociferous.server.client import (
            DEFAULT_DAEMON_HOST,
            DEFAULT_DAEMON_PORT,
            DEFAULT_TIMEOUT_S,
        )
        
        # Localhost only (security)
        assert DEFAULT_DAEMON_HOST == "127.0.0.1"
        # Reasonable port
        assert 1024 < DEFAULT_DAEMON_PORT < 65535
        # Reasonable timeout (enough for model inference)
        assert 30 <= DEFAULT_TIMEOUT_S <= 600


class TestExceptionHierarchy:
    """Test exception types for proper error handling."""

    def test_daemon_error_is_base_exception(self) -> None:
        """Test DaemonError is the base for all daemon exceptions."""
        from vociferous.domain.exceptions import VociferousError
        from vociferous.server.client import (
            DaemonError,
        )
        
        # DaemonError should inherit from VociferousError
        assert issubclass(DaemonError, VociferousError)

    def test_not_running_error_inheritance(self) -> None:
        """Test DaemonNotRunningError inherits from DaemonError."""
        from vociferous.server.client import DaemonError, DaemonNotRunningError
        
        assert issubclass(DaemonNotRunningError, DaemonError)
        
        # Should be catchable as DaemonError
        try:
            raise DaemonNotRunningError()
        except DaemonError:
            pass  # Should be caught

    def test_timeout_error_inheritance(self) -> None:
        """Test DaemonTimeoutError inherits from DaemonError."""
        from vociferous.server.client import DaemonError, DaemonTimeoutError
        
        assert issubclass(DaemonTimeoutError, DaemonError)
        
        # Should be catchable as DaemonError
        try:
            raise DaemonTimeoutError()
        except DaemonError:
            pass  # Should be caught

    def test_exception_messages(self) -> None:
        """Test exceptions can have custom messages."""
        from vociferous.server.client import (
            DaemonError,
            DaemonNotRunningError,
            DaemonTimeoutError,
        )
        
        assert str(DaemonError("Custom error")) == "Custom error"
        assert str(DaemonNotRunningError("Not running")) == "Not running"
        assert str(DaemonTimeoutError("Timed out")) == "Timed out"


class TestPidFileHandling:
    """Test PID file operations (real file operations, no mocks)."""

    def test_get_daemon_pid_no_file(self, tmp_path: Path) -> None:
        """Test get_daemon_pid returns None if no PID file."""
        from vociferous.server.client import get_daemon_pid
        
        result = get_daemon_pid(pid_file=tmp_path / "nonexistent.pid")
        assert result is None

    def test_get_daemon_pid_invalid_content(self, tmp_path: Path) -> None:
        """Test get_daemon_pid returns None for invalid PID file."""
        from vociferous.server.client import get_daemon_pid
        
        pid_file = tmp_path / "daemon.pid"
        pid_file.write_text("not a number")
        
        result = get_daemon_pid(pid_file=pid_file)
        assert result is None

    def test_get_daemon_pid_empty_file(self, tmp_path: Path) -> None:
        """Test get_daemon_pid returns None for empty PID file."""
        from vociferous.server.client import get_daemon_pid
        
        pid_file = tmp_path / "daemon.pid"
        pid_file.write_text("")
        
        result = get_daemon_pid(pid_file=pid_file)
        assert result is None

    def test_get_daemon_pid_whitespace_only(self, tmp_path: Path) -> None:
        """Test get_daemon_pid handles whitespace-only file."""
        from vociferous.server.client import get_daemon_pid
        
        pid_file = tmp_path / "daemon.pid"
        pid_file.write_text("   \n\t  ")
        
        result = get_daemon_pid(pid_file=pid_file)
        assert result is None

    def test_get_daemon_pid_stale_pid(self, tmp_path: Path) -> None:
        """Test get_daemon_pid returns None for non-existent process."""
        from vociferous.server.client import get_daemon_pid
        
        pid_file = tmp_path / "daemon.pid"
        pid_file.write_text("999999999")  # PID that definitely doesn't exist
        
        result = get_daemon_pid(pid_file=pid_file)
        assert result is None

    def test_get_daemon_pid_valid_current_process(self, tmp_path: Path) -> None:
        """Test get_daemon_pid returns PID for running process."""
        from vociferous.server.client import get_daemon_pid
        
        pid_file = tmp_path / "daemon.pid"
        # Use current process PID (guaranteed to be running)
        current_pid = os.getpid()
        pid_file.write_text(str(current_pid))
        
        result = get_daemon_pid(pid_file=pid_file)
        assert result == current_pid

    def test_get_daemon_pid_with_newline(self, tmp_path: Path) -> None:
        """Test get_daemon_pid handles PID with trailing newline."""
        from vociferous.server.client import get_daemon_pid
        
        pid_file = tmp_path / "daemon.pid"
        current_pid = os.getpid()
        pid_file.write_text(f"{current_pid}\n")
        
        result = get_daemon_pid(pid_file=pid_file)
        assert result == current_pid


class TestTranscribeFileValidation:
    """Test client input validation (no network needed)."""

    def test_transcribe_rejects_missing_file(self, tmp_path: Path) -> None:
        """Test transcribe raises FileNotFoundError for missing file."""
        from vociferous.server.client import DaemonClient
        
        client = DaemonClient()
        
        with pytest.raises(FileNotFoundError):
            client.transcribe(tmp_path / "nonexistent.wav")

    def test_batch_transcribe_rejects_missing_file(self, tmp_path: Path) -> None:
        """Test batch_transcribe raises FileNotFoundError for any missing file."""
        from vociferous.server.client import DaemonClient
        
        existing = tmp_path / "existing.wav"
        existing.write_bytes(b"audio")
        missing = tmp_path / "missing.wav"
        
        client = DaemonClient()
        
        with pytest.raises(FileNotFoundError):
            client.batch_transcribe([existing, missing])


class TestDefaultPaths:
    """Test default path configurations."""

    def test_pid_file_location(self) -> None:
        """Test PID file is in user cache directory."""
        from vociferous.server.client import PID_FILE
        
        assert "cache" in str(PID_FILE).lower() or ".cache" in str(PID_FILE)
        assert "vociferous" in str(PID_FILE)

    def test_cache_dir_location(self) -> None:
        """Test cache dir is in home directory."""
        from vociferous.server.client import CACHE_DIR
        
        home = Path.home()
        assert str(CACHE_DIR).startswith(str(home))


class TestConvenienceFunctionBehavior:
    """Test convenience function behavior without network.
    
    These test the fallback behavior - actual daemon tests are in integration.
    """

    def test_transcribe_via_daemon_raises_for_missing_file(self, tmp_path: Path) -> None:
        """Test transcribe_via_daemon raises FileNotFoundError for missing file.
        
        Note: Missing file is a user error, not a daemon error, so it raises.
        """
        from vociferous.server.client import transcribe_via_daemon
        
        with pytest.raises(FileNotFoundError):
            transcribe_via_daemon(tmp_path / "missing.wav")

    def test_convenience_functions_exist(self) -> None:
        """Test all convenience functions are exported."""
        from vociferous.server.client import (
            batch_transcribe_via_daemon,
            get_daemon_pid,
            is_daemon_running,
            refine_via_daemon,
            transcribe_via_daemon,
        )
        
        # All should be callable
        assert callable(transcribe_via_daemon)
        assert callable(refine_via_daemon)
        assert callable(batch_transcribe_via_daemon)
        assert callable(is_daemon_running)
        assert callable(get_daemon_pid)
