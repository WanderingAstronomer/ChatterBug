"""Warm model server for fast inference.

The daemon keeps the Canary-Qwen model loaded in GPU memory,
eliminating the ~16s model loading overhead for each transcription.

Usage:
    vociferous daemon start   # Start the warm model server
    vociferous daemon stop    # Stop the server
    vociferous daemon status  # Check server status
    
    # Transcribe using warm model (automatic if daemon is running)
    vociferous transcribe audio.wav

Programmatic usage:
    from vociferous.server import DaemonClient, is_daemon_running
    
    if is_daemon_running():
        client = DaemonClient()
        segments = client.transcribe([Path("audio.wav")])
"""

from vociferous.server.client import (
    DaemonClient,
    is_daemon_running,
    get_daemon_pid,
    transcribe_via_daemon,
)
from vociferous.server.protocol import (
    TranscribeRequest,
    TranscribeResponse,
    StatusRequest,
    StatusResponse,
    DEFAULT_SOCKET_PATH,
    DEFAULT_PID_FILE,
)
from vociferous.server.daemon import run_daemon, WarmModelDaemon

__all__ = [
    # Client
    "DaemonClient",
    "is_daemon_running",
    "get_daemon_pid",
    "transcribe_via_daemon",
    # Protocol
    "TranscribeRequest",
    "TranscribeResponse",
    "StatusRequest",
    "StatusResponse",
    "DEFAULT_SOCKET_PATH",
    "DEFAULT_PID_FILE",
    # Daemon
    "run_daemon",
    "WarmModelDaemon",
]
