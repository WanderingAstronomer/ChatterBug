"""Tests for daemon CLI commands and detection.

These tests cover the CLI command logic and daemon detection helpers.
The actual server tests are in test_api.py and test_client.py.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

from vociferous.server.client import get_daemon_pid, is_daemon_running


class TestDaemonDetection:
    """Test daemon running detection via HTTP health check."""

    @patch("vociferous.server.client.requests.get")
    def test_daemon_running_healthy(self, mock_get: Mock) -> None:
        """Daemon should be detected as running if health check succeeds."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"model_loaded": True}
        mock_get.return_value = mock_response

        assert is_daemon_running() is True

    @patch("vociferous.server.client.requests.get")
    def test_daemon_not_running_connection_refused(self, mock_get: Mock) -> None:
        """Daemon should be detected as not running on connection error."""
        from requests.exceptions import ConnectionError

        mock_get.side_effect = ConnectionError()

        assert is_daemon_running() is False

    @patch("vociferous.server.client.requests.get")
    def test_daemon_not_running_timeout(self, mock_get: Mock) -> None:
        """Daemon should be detected as not running on timeout."""
        from requests.exceptions import Timeout

        mock_get.side_effect = Timeout()

        assert is_daemon_running() is False

    @patch("vociferous.server.client.requests.get")
    def test_daemon_running_but_model_not_loaded(self, mock_get: Mock) -> None:
        """Daemon should be detected as not running if model not loaded."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"model_loaded": False}
        mock_get.return_value = mock_response

        assert is_daemon_running() is False


class TestPIDFileManagement:
    """Test PID file reading and validation."""

    def test_get_daemon_pid_no_file(self, tmp_path: Path) -> None:
        """get_daemon_pid should return None if PID file doesn't exist."""
        pid_file = tmp_path / "nonexistent.pid"
        assert get_daemon_pid(pid_file=pid_file) is None

    def test_get_daemon_pid_invalid_content(self, tmp_path: Path) -> None:
        """get_daemon_pid should return None for invalid PID content."""
        pid_file = tmp_path / "test.pid"
        pid_file.write_text("not a number")
        assert get_daemon_pid(pid_file=pid_file) is None

    def test_get_daemon_pid_stale_pid(self, tmp_path: Path) -> None:
        """get_daemon_pid should return None for stale (dead) process."""
        pid_file = tmp_path / "test.pid"
        # Write a PID that definitely doesn't exist
        pid_file.write_text("999999999")
        assert get_daemon_pid(pid_file=pid_file) is None

    def test_get_daemon_pid_empty_file(self, tmp_path: Path) -> None:
        """get_daemon_pid should return None for empty PID file."""
        pid_file = tmp_path / "test.pid"
        pid_file.write_text("")
        assert get_daemon_pid(pid_file=pid_file) is None


class TestDefaultPaths:
    """Test default configuration values."""

    def test_default_host(self) -> None:
        from vociferous.server.client import DEFAULT_DAEMON_HOST

        assert DEFAULT_DAEMON_HOST == "127.0.0.1"

    def test_default_port(self) -> None:
        from vociferous.server.client import DEFAULT_DAEMON_PORT

        assert DEFAULT_DAEMON_PORT == 8765

    def test_default_timeout(self) -> None:
        from vociferous.server.client import DEFAULT_TIMEOUT_S

        assert DEFAULT_TIMEOUT_S == 60.0

    def test_pid_file_in_cache(self) -> None:
        from vociferous.server.client import CACHE_DIR, PID_FILE

        assert PID_FILE.parent == CACHE_DIR
        assert PID_FILE.name == "daemon.pid"


class TestExceptionHierarchy:
    """Test exception class hierarchy."""

    def test_daemon_error_is_vociferous_error(self) -> None:
        from vociferous.domain.exceptions import VociferousError
        from vociferous.server.client import DaemonError

        assert issubclass(DaemonError, VociferousError)

    def test_daemon_not_running_is_daemon_error(self) -> None:
        from vociferous.server.client import DaemonError, DaemonNotRunningError

        assert issubclass(DaemonNotRunningError, DaemonError)

    def test_daemon_timeout_is_daemon_error(self) -> None:
        from vociferous.server.client import DaemonError, DaemonTimeoutError

        assert issubclass(DaemonTimeoutError, DaemonError)
