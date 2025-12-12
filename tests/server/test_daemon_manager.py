"""Tests for DaemonManager with auto-start capability."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from vociferous.server.manager import (
    DaemonManager,
    DaemonStartError,
    _get_daemon_pid,
    ensure_daemon_running,
)


class TestDaemonManager:
    """Tests for DaemonManager class."""

    def test_init_default_values(self):
        """DaemonManager initializes with default host/port."""
        manager = DaemonManager()
        assert manager.host == "127.0.0.1"
        assert manager.port == 8765
        assert manager.timeout == 60.0

    def test_init_custom_values(self):
        """DaemonManager accepts custom host/port/timeout."""
        manager = DaemonManager(host="0.0.0.0", port=9000, timeout=120.0)
        assert manager.host == "0.0.0.0"
        assert manager.port == 9000
        assert manager.timeout == 120.0

    def test_client_property_lazy_creation(self):
        """Client is lazily created on first access."""
        manager = DaemonManager()
        assert manager._client is None
        
        client = manager.client
        assert client is not None
        assert manager._client is client
        
        # Same instance returned on subsequent access
        assert manager.client is client

    @patch("vociferous.server.manager.DaemonClient")
    def test_is_running_returns_client_ping(self, mock_client_cls):
        """is_running delegates to client.ping()."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client_cls.return_value = mock_client

        manager = DaemonManager()
        result = manager.is_running()

        assert result is True
        mock_client.ping.assert_called_once()

    @patch("vociferous.server.manager.DaemonClient")
    def test_is_running_returns_false_when_not_running(self, mock_client_cls):
        """is_running returns False when daemon not running."""
        mock_client = Mock()
        mock_client.ping.return_value = False
        mock_client_cls.return_value = mock_client

        manager = DaemonManager()
        result = manager.is_running()

        assert result is False

    @patch("vociferous.server.manager.DaemonClient")
    def test_ensure_running_returns_true_when_already_running(self, mock_client_cls):
        """ensure_running returns True if daemon already running."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client_cls.return_value = mock_client

        manager = DaemonManager()
        result = manager.ensure_running(auto_start=True)

        assert result is True

    @patch("vociferous.server.manager.DaemonClient")
    def test_ensure_running_returns_false_when_auto_start_disabled(self, mock_client_cls):
        """ensure_running returns False if not running and auto_start=False."""
        mock_client = Mock()
        mock_client.ping.return_value = False
        mock_client_cls.return_value = mock_client

        manager = DaemonManager()
        result = manager.ensure_running(auto_start=False)

        assert result is False

    @patch("vociferous.server.manager._get_daemon_pid")
    @patch("vociferous.server.manager._remove_pid_file")
    @patch("vociferous.server.manager._ensure_cache_dir")
    @patch("vociferous.server.manager.subprocess.Popen")
    @patch("vociferous.server.manager._write_pid_file")
    @patch("vociferous.server.manager.time.sleep")
    @patch("vociferous.server.manager.DaemonClient")
    def test_start_sync_success(
        self,
        mock_client_cls,
        mock_sleep,
        mock_write_pid,
        mock_popen,
        mock_cache_dir,
        mock_remove_pid,
        mock_get_pid,
    ):
        """start_sync successfully starts daemon and waits for health."""
        mock_client = Mock()
        # First call returns False (daemon starting), second returns True (daemon ready)
        mock_client.ping.side_effect = [False, True]
        mock_client_cls.return_value = mock_client

        mock_proc = Mock()
        mock_proc.pid = 12345
        mock_popen.return_value = mock_proc

        manager = DaemonManager()
        pid = manager.start_sync(timeout=10.0)

        assert pid == 12345
        mock_write_pid.assert_called_once_with(12345)

    @patch("vociferous.server.manager._remove_pid_file")
    @patch("vociferous.server.manager._ensure_cache_dir")
    @patch("vociferous.server.manager.subprocess.Popen")
    @patch("vociferous.server.manager.time.sleep")
    @patch("vociferous.server.manager.DaemonClient")
    @patch("vociferous.server.manager.LOG_FILE")
    def test_start_sync_timeout_raises_error(
        self,
        mock_log_file,
        mock_client_cls,
        mock_sleep,
        mock_popen,
        mock_cache_dir,
        mock_remove_pid,
    ):
        """start_sync raises DaemonStartError on timeout."""
        mock_client = Mock()
        mock_client.ping.return_value = False  # Never becomes healthy
        mock_client_cls.return_value = mock_client

        mock_proc = Mock()
        mock_proc.pid = 12345
        mock_popen.return_value = mock_proc
        
        # Mock log file
        mock_log_file.exists.return_value = False

        manager = DaemonManager()

        with pytest.raises(DaemonStartError) as exc_info:
            manager.start_sync(timeout=2.0)  # Very short timeout

        assert "failed to start" in str(exc_info.value).lower()
        mock_proc.kill.assert_called_once()


class TestEnsureDaemonRunning:
    """Tests for convenience function."""

    @patch("vociferous.server.manager.DaemonManager")
    def test_ensure_daemon_running_delegates_to_manager(self, mock_manager_cls):
        """ensure_daemon_running creates manager and calls ensure_running."""
        mock_manager = Mock()
        mock_manager.ensure_running.return_value = True
        mock_manager_cls.return_value = mock_manager

        result = ensure_daemon_running(auto_start=True, progress=None)

        assert result is True
        mock_manager.ensure_running.assert_called_once_with(
            auto_start=True,
            progress=None,
        )


class TestGetDaemonPid:
    """Tests for _get_daemon_pid helper."""

    @patch("vociferous.server.manager.PID_FILE")
    def test_returns_none_when_no_pid_file(self, mock_pid_file):
        """Returns None when PID file doesn't exist."""
        mock_pid_file.exists.return_value = False
        
        result = _get_daemon_pid()
        
        assert result is None

    @patch("vociferous.server.manager.os.kill")
    @patch("vociferous.server.manager.PID_FILE")
    def test_returns_pid_when_valid_and_process_exists(self, mock_pid_file, mock_kill):
        """Returns PID when file is valid and process exists."""
        mock_pid_file.exists.return_value = True
        mock_pid_file.read_text.return_value = "12345"
        mock_kill.return_value = None  # Process exists

        result = _get_daemon_pid()

        assert result == 12345
        mock_kill.assert_called_once_with(12345, 0)

    @patch("vociferous.server.manager._remove_pid_file")
    @patch("vociferous.server.manager.os.kill")
    @patch("vociferous.server.manager.PID_FILE")
    def test_returns_none_and_cleans_stale_pid(self, mock_pid_file, mock_kill, mock_remove):
        """Returns None and removes stale PID file when process doesn't exist."""
        mock_pid_file.exists.return_value = True
        mock_pid_file.read_text.return_value = "12345"
        mock_kill.side_effect = ProcessLookupError()

        result = _get_daemon_pid()

        assert result is None
        mock_remove.assert_called_once()
