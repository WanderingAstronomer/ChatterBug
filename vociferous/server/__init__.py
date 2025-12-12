"""Warm model server for fast inference (FastAPI + uvicorn).

The daemon keeps the Canary-Qwen model loaded in GPU memory,
eliminating the ~16s model loading overhead for each transcription.

Usage:
    vociferous daemon start   # Start the warm model server
    vociferous daemon stop    # Stop the server
    vociferous daemon status  # Check server status
    
    # Transcribe using warm model (use --use-daemon flag)
    vociferous transcribe audio.wav --use-daemon

Programmatic usage:
    from vociferous.server import DaemonClient, is_daemon_running
    
    if is_daemon_running():
        client = DaemonClient()
        segments = client.transcribe(Path("audio.wav"))
"""

from vociferous.server.client import (
    CACHE_DIR,
    DEFAULT_DAEMON_HOST,
    DEFAULT_DAEMON_PORT,
    PID_FILE,
    DaemonClient,
    DaemonError,
    DaemonNotRunningError,
    DaemonTimeoutError,
    batch_transcribe_via_daemon,
    get_daemon_pid,
    is_daemon_running,
    refine_via_daemon,
    transcribe_via_daemon,
)
from vociferous.server.manager import (
    AsyncStartupResult,
    DaemonManager,
    DaemonStartError,
    ensure_daemon_running,
)

__all__ = [
    "AsyncStartupResult",
    "CACHE_DIR",
    "DEFAULT_DAEMON_HOST",
    "DEFAULT_DAEMON_PORT",
    "PID_FILE",
    "DaemonClient",
    "DaemonError",
    "DaemonManager",
    "DaemonNotRunningError",
    "DaemonStartError",
    "DaemonTimeoutError",
    "batch_transcribe_via_daemon",
    "ensure_daemon_running",
    "get_daemon_pid",
    "is_daemon_running",
    "refine_via_daemon",
    "transcribe_via_daemon",
]
