"""Daemon lifecycle management with auto-start capability.

Provides smart daemon management that can automatically start the daemon
when needed, with progress integration for UI feedback.

Usage:
    from vociferous.server.manager import DaemonManager
    
    manager = DaemonManager()
    
    # Ensure daemon is running (auto-start if needed)
    if manager.ensure_running(auto_start=True):
        segments = manager.client.transcribe(audio_path)
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from vociferous.server.client import (
    DEFAULT_DAEMON_HOST,
    DEFAULT_DAEMON_PORT,
    DaemonClient,
    DaemonError,
)

if TYPE_CHECKING:
    from vociferous.app.progress import ProgressTracker

logger = logging.getLogger(__name__)

# Daemon configuration
DAEMON_MODULE = "vociferous.server.api:app"
CACHE_DIR = Path.home() / ".cache" / "vociferous"
PID_FILE = CACHE_DIR / "daemon.pid"
LOG_FILE = CACHE_DIR / "daemon.log"


class DaemonStartError(DaemonError):
    """Raised when daemon fails to start."""
    pass


def _ensure_cache_dir() -> None:
    """Ensure cache directory exists."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _write_pid_file(pid: int) -> None:
    """Write daemon PID to PID file."""
    _ensure_cache_dir()
    PID_FILE.write_text(str(pid))


def _remove_pid_file() -> None:
    """Remove PID file."""
    PID_FILE.unlink(missing_ok=True)


def _get_daemon_pid() -> int | None:
    """Read daemon PID from PID file.

    Returns:
        PID if valid and process exists, None otherwise
    """
    if not PID_FILE.exists():
        return None

    try:
        pid = int(PID_FILE.read_text().strip())
        # Check if process is actually running
        os.kill(pid, 0)  # Signal 0 just checks if process exists
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        # PID file is stale or invalid
        _remove_pid_file()
        return None


class DaemonManager:
    """Manages daemon lifecycle with auto-start capability.

    Provides a unified interface for starting, stopping, and checking
    daemon status, with optional auto-start when daemon is needed but
    not running.

    Args:
        host: Daemon host address (default: 127.0.0.1)
        port: Daemon port number (default: 8765)
        timeout: Request timeout in seconds (default: 60.0)

    Example:
        manager = DaemonManager()
        
        # Check and optionally auto-start
        if manager.ensure_running(auto_start=True):
            segments = manager.client.transcribe(audio_path)
        else:
            # Daemon not available, use direct engine
            pass
    """

    def __init__(
        self,
        host: str = DEFAULT_DAEMON_HOST,
        port: int = DEFAULT_DAEMON_PORT,
        timeout: float = 60.0,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._client: DaemonClient | None = None

    @property
    def client(self) -> DaemonClient:
        """Get or create the daemon client."""
        if self._client is None:
            self._client = DaemonClient(
                host=self.host,
                port=self.port,
                timeout=self.timeout,
            )
        return self._client

    def is_running(self) -> bool:
        """Check if daemon is running and healthy.

        Returns:
            True if daemon is running and model is loaded
        """
        return self.client.ping()

    def get_pid(self) -> int | None:
        """Get daemon PID if running.

        Returns:
            PID if daemon is running, None otherwise
        """
        return _get_daemon_pid()

    def ensure_running(
        self,
        auto_start: bool = True,
        progress: ProgressTracker | None = None,
    ) -> bool:
        """Ensure daemon is running, optionally auto-starting it.

        Args:
            auto_start: If True, start daemon if not running
            progress: Optional progress tracker for UI feedback

        Returns:
            True if daemon is running (or was started successfully)
            False if daemon is not running and auto_start is disabled or failed
        """
        # Check if already running
        if self.is_running():
            logger.debug("Daemon is already running")
            return True

        # Not running - auto-start if requested
        if not auto_start:
            logger.debug("Daemon not running, auto-start disabled")
            return False

        if progress:
            progress.print("Daemon not running, starting automatically...")

        try:
            self.start_sync(progress=progress)
            return True

        except DaemonStartError as e:
            logger.error(f"Failed to auto-start daemon: {e}")

            if progress:
                progress.print(f"⚠️ Daemon auto-start failed: {e}", style="yellow")

            return False

    def start_sync(
        self,
        timeout: float = 60.0,
        progress: ProgressTracker | None = None,
    ) -> int:
        """Start daemon and wait for it to be ready.

        Args:
            timeout: Maximum time to wait for daemon to be ready
            progress: Optional progress tracker for UI feedback

        Returns:
            PID of started daemon process

        Raises:
            DaemonStartError: If daemon fails to start within timeout
        """
        # Clean up stale PID file
        _remove_pid_file()
        _ensure_cache_dir()

        task_id = None
        if progress:
            task_id = progress.add_step("Starting warm model daemon...", total=100)

        # Prepare uvicorn command
        cmd = [
            sys.executable, "-m", "uvicorn",
            DAEMON_MODULE,
            "--host", self.host,
            "--port", str(self.port),
            "--log-level", "info",
        ]

        # Start daemon process in background
        with open(LOG_FILE, "w") as log_file:
            proc = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # Detach from terminal
            )

        _write_pid_file(proc.pid)
        logger.info(f"Started daemon process with PID {proc.pid}")

        # Wait for health check
        start_time = time.time()
        check_interval = 1.0
        last_progress_update = 0

        while time.time() - start_time < timeout:
            time.sleep(check_interval)
            elapsed = time.time() - start_time

            # Update progress (estimate based on typical load time of ~16s)
            if progress and task_id is not None:
                progress_pct = min(90, (elapsed / 16.0) * 90)
                if elapsed - last_progress_update >= 2.0:
                    progress.update(task_id, completed=int(progress_pct))
                    last_progress_update = elapsed

            if self.is_running():
                if progress and task_id is not None:
                    progress.update(task_id, completed=100)
                    progress.complete(task_id)
                    progress.print(f"✓ Daemon started successfully (PID: {proc.pid})")

                logger.info(f"Daemon started successfully (PID: {proc.pid})")
                return proc.pid

        # Timeout - daemon didn't start
        if progress and task_id is not None:
            progress.complete(task_id)

        proc.kill()
        _remove_pid_file()

        error_msg = f"Daemon failed to start within {timeout}s"
        
        # Try to get error from log file
        if LOG_FILE.exists():
            try:
                log_content = LOG_FILE.read_text()
                if "Error" in log_content or "error" in log_content:
                    # Extract last few lines for context
                    lines = log_content.strip().split("\n")
                    error_lines = lines[-5:] if len(lines) > 5 else lines
                    error_msg += "\nLog output:\n" + "\n".join(error_lines)
            except Exception:
                pass

        raise DaemonStartError(error_msg)

    def stop(self, timeout: float = 10.0) -> bool:
        """Stop the daemon gracefully.

        Args:
            timeout: Maximum time to wait for daemon to stop

        Returns:
            True if daemon was stopped successfully, False if wasn't running
        """
        pid = _get_daemon_pid()

        if not pid:
            if self.is_running():
                logger.warning("Daemon is running but PID file not found")
                return False
            return True  # Already stopped

        logger.info(f"Stopping daemon (PID: {pid})...")

        try:
            # Send SIGTERM for graceful shutdown
            os.kill(pid, signal.SIGTERM)

            # Wait for shutdown
            start_time = time.time()
            while time.time() - start_time < timeout:
                time.sleep(0.5)
                try:
                    os.kill(pid, 0)  # Check if still running
                except ProcessLookupError:
                    _remove_pid_file()
                    logger.info("Daemon stopped successfully")
                    return True

            # Force kill if still running
            logger.warning("Daemon didn't stop gracefully, force killing...")
            os.kill(pid, signal.SIGKILL)
            _remove_pid_file()
            return True

        except ProcessLookupError:
            _remove_pid_file()
            return True

        except PermissionError as e:
            logger.error(f"Permission denied stopping daemon: {e}")
            return False

    def restart(
        self,
        timeout: float = 60.0,
        progress: ProgressTracker | None = None,
    ) -> int:
        """Restart the daemon.

        Args:
            timeout: Maximum time to wait for daemon to restart
            progress: Optional progress tracker for UI feedback

        Returns:
            PID of restarted daemon process
        """
        self.stop()
        return self.start_sync(timeout=timeout, progress=progress)


# ============================================================================
# Convenience Functions
# ============================================================================


def ensure_daemon_running(
    auto_start: bool = True,
    progress: ProgressTracker | None = None,
) -> bool:
    """Convenience function to ensure daemon is running.

    Args:
        auto_start: If True, start daemon if not running
        progress: Optional progress tracker for UI feedback

    Returns:
        True if daemon is running or was started successfully
    """
    manager = DaemonManager()
    return manager.ensure_running(auto_start=auto_start, progress=progress)
