"""Tests for async daemon startup.

These tests verify that the async daemon startup works correctly
for GUI use cases where blocking is unacceptable.
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from vociferous.server.manager import (
    AsyncStartupResult,
    DaemonManager,
)


class TestAsyncStartupResult:
    """Tests for AsyncStartupResult data class."""

    def test_initial_state(self) -> None:
        """Test AsyncStartupResult is not complete initially."""
        result = AsyncStartupResult()

        assert result.success is None
        assert result.pid is None
        assert result.error is None
        assert result.is_complete is False
        # Not running since no thread set
        assert result.is_running is False

    def test_success_state(self) -> None:
        """Test AsyncStartupResult tracks success."""
        result = AsyncStartupResult()
        result._complete(success=True, pid=12345)

        assert result.success is True
        assert result.pid == 12345
        assert result.error is None
        assert result.is_complete is True

    def test_failure_state(self) -> None:
        """Test AsyncStartupResult tracks failure."""
        result = AsyncStartupResult()
        result._complete(success=False, error="Timeout")

        assert result.success is False
        assert result.pid is None
        assert result.error == "Timeout"
        assert result.is_complete is True

    def test_is_running_with_active_thread(self) -> None:
        """Test is_running returns True while thread is alive."""
        result = AsyncStartupResult()

        # Create a thread that waits
        event = threading.Event()

        def wait_for_event() -> None:
            event.wait()

        thread = threading.Thread(target=wait_for_event)
        result._set_thread(thread)
        thread.start()

        try:
            assert result.is_running is True
        finally:
            event.set()
            thread.join()

        assert result.is_running is False

    def test_wait_returns_immediately_when_complete(self) -> None:
        """Test wait() returns quickly when already complete."""
        result = AsyncStartupResult()
        result._complete(success=True, pid=123)

        start = time.time()
        completed = result.wait(timeout=5.0)
        elapsed = time.time() - start

        assert completed is True
        assert elapsed < 1.0

    def test_wait_blocks_until_completion(self) -> None:
        """Test wait() blocks until thread finishes."""
        result = AsyncStartupResult()

        def quick_task() -> None:
            time.sleep(0.2)
            result._complete(success=True, pid=456)

        thread = threading.Thread(target=quick_task)
        result._set_thread(thread)
        thread.start()

        completed = result.wait(timeout=5.0)

        assert completed is True
        assert result.success is True
        assert result.pid == 456

    def test_wait_timeout_returns_false(self) -> None:
        """Test wait() returns False on timeout."""
        result = AsyncStartupResult()
        event = threading.Event()

        def slow_task() -> None:
            event.wait()

        thread = threading.Thread(target=slow_task)
        result._set_thread(thread)
        thread.start()

        try:
            completed = result.wait(timeout=0.1)
            assert completed is False
            assert result.is_running is True
        finally:
            event.set()
            thread.join()


class TestStartAsyncNonBlocking:
    """Tests that start_async() is non-blocking."""

    def test_start_async_returns_immediately(self) -> None:
        """Test that start_async returns immediately (non-blocking)."""
        manager = DaemonManager()

        # Mock subprocess to not actually start anything
        with patch("vociferous.server.manager.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            start_time = time.time()
            result = manager.start_async()
            call_time = time.time() - start_time

            # Should return in < 1 second (not wait for model load)
            assert call_time < 1.0

            # Result should be an AsyncStartupResult
            assert isinstance(result, AsyncStartupResult)

            # Thread should be running (or at least started)
            assert result._thread is not None

    def test_start_async_calls_progress_callback(self) -> None:
        """Test that progress callback is called."""
        manager = DaemonManager(timeout=2.0)
        callbacks: list[tuple[str, float]] = []

        def progress_callback(msg: str, elapsed: float) -> None:
            callbacks.append((msg, elapsed))

        # Mock to avoid real process startup
        with patch("vociferous.server.manager.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            result = manager.start_async(
                progress_callback=progress_callback,
                timeout=1.0,  # Short timeout for test
            )

            # Wait for completion (will timeout since mock isn't a real daemon)
            result.wait(timeout=3.0)

        # Should have received at least one callback
        assert len(callbacks) > 0

        # First callback should be "Starting daemon..."
        first_msg, first_elapsed = callbacks[0]
        assert "Starting" in first_msg
        assert first_elapsed >= 0.0

    def test_start_async_without_callback_works(self) -> None:
        """Test start_async works without callback."""
        manager = DaemonManager(timeout=1.0)

        with patch("vociferous.server.manager.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            result = manager.start_async(progress_callback=None, timeout=1.0)

            # Should return immediately
            assert isinstance(result, AsyncStartupResult)
            assert result._thread is not None


class TestStartAsyncWithMockedDaemon:
    """Tests using mocked daemon for quick execution."""

    def test_async_startup_success(self) -> None:
        """Test successful async startup."""
        manager = DaemonManager(timeout=5.0)
        callbacks: list[tuple[str, float]] = []

        def progress_callback(msg: str, elapsed: float) -> None:
            callbacks.append((msg, elapsed))

        # Mock both Popen and is_running
        with (
            patch("vociferous.server.manager.subprocess.Popen") as mock_popen,
            patch.object(manager, "is_running") as mock_is_running,
        ):
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            # First call returns False, second returns True
            mock_is_running.side_effect = [False, True]

            result = manager.start_async(
                progress_callback=progress_callback,
                timeout=10.0,
            )
            result.wait(timeout=5.0)

        # Should have succeeded
        assert result.success is True
        assert result.pid == 12345
        assert result.error is None

        # Should have final success message
        assert any("ready" in msg.lower() or "✓" in msg for msg, _ in callbacks)

    def test_async_startup_timeout(self) -> None:
        """Test async startup handles timeout."""
        manager = DaemonManager(timeout=2.0)
        callbacks: list[tuple[str, float]] = []

        def progress_callback(msg: str, elapsed: float) -> None:
            callbacks.append((msg, elapsed))

        with (
            patch("vociferous.server.manager.subprocess.Popen") as mock_popen,
            patch.object(manager, "is_running", return_value=False),
        ):
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            result = manager.start_async(
                progress_callback=progress_callback,
                timeout=1.5,
            )
            result.wait(timeout=5.0)

        # Should have failed
        assert result.success is False
        assert result.pid is None
        assert result.error is not None
        assert "failed" in result.error.lower() or "timeout" in result.error.lower()

        # Process should have been killed
        mock_proc.kill.assert_called_once()

    def test_async_startup_thread_is_daemon(self) -> None:
        """Test that startup thread is a daemon thread."""
        manager = DaemonManager(timeout=1.0)

        with patch("vociferous.server.manager.subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            result = manager.start_async(timeout=1.0)

            # Thread should be a daemon (won't prevent program exit)
            assert result._thread is not None
            assert result._thread.daemon is True


class TestProgressCallbackContract:
    """Tests verifying the progress callback contract."""

    def test_elapsed_time_increases(self) -> None:
        """Test elapsed time in callbacks increases over time."""
        manager = DaemonManager(timeout=3.0)
        elapsed_times: list[float] = []

        def progress_callback(msg: str, elapsed: float) -> None:
            elapsed_times.append(elapsed)

        with (
            patch("vociferous.server.manager.subprocess.Popen") as mock_popen,
            patch.object(manager, "is_running", return_value=False),
        ):
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc

            result = manager.start_async(
                progress_callback=progress_callback,
                timeout=2.0,
            )
            result.wait(timeout=5.0)

        # Should have multiple elapsed time values
        assert len(elapsed_times) >= 2

        # Elapsed times should generally increase
        # (allow some tolerance for timing)
        assert elapsed_times[-1] >= elapsed_times[0]

    def test_callback_messages_are_informative(self) -> None:
        """Test callback messages provide useful information."""
        manager = DaemonManager(timeout=2.0)
        messages: list[str] = []

        def progress_callback(msg: str, elapsed: float) -> None:
            messages.append(msg)

        with (
            patch("vociferous.server.manager.subprocess.Popen") as mock_popen,
            patch.object(manager, "is_running") as mock_is_running,
        ):
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc
            mock_is_running.side_effect = [False, True]

            result = manager.start_async(
                progress_callback=progress_callback,
                timeout=5.0,
            )
            result.wait(timeout=5.0)

        # Should have received messages
        assert len(messages) >= 2

        # Messages should be non-empty strings
        for msg in messages:
            assert isinstance(msg, str)
            assert len(msg) > 0


class TestThreadSafety:
    """Tests for thread safety of AsyncStartupResult."""

    def test_concurrent_access_to_result(self) -> None:
        """Test that result can be safely accessed from multiple threads."""
        result = AsyncStartupResult()
        reads: list[bool | None] = []
        errors: list[Exception] = []

        def reader() -> None:
            try:
                for _ in range(100):
                    _ = result.success
                    _ = result.pid
                    _ = result.is_complete
                    reads.append(result.success)
            except Exception as e:
                errors.append(e)

        def writer() -> None:
            try:
                time.sleep(0.01)
                result._complete(success=True, pid=999)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=reader),
            threading.Thread(target=writer),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should have occurred
        assert len(errors) == 0

        # Final state should be consistent
        assert result.success is True
        assert result.pid == 999
