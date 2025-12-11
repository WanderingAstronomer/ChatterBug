"""Client for communicating with the warm model daemon."""

from __future__ import annotations

import asyncio
import json
import os
import socket
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

from vociferous.server.protocol import (
    DEFAULT_SOCKET_PATH,
    DEFAULT_PID_FILE,
    TranscribeRequest,
    TranscribeResponse,
    StatusRequest,
    StatusResponse,
    ShutdownRequest,
    ShutdownResponse,
)

if TYPE_CHECKING:
    from vociferous.domain.model import TranscriptSegment


def is_daemon_running(
    socket_path: Path = DEFAULT_SOCKET_PATH,
    pid_file: Path = DEFAULT_PID_FILE,
) -> bool:
    """Check if the daemon is running.
    
    Checks both the PID file and socket availability.
    """
    # Check PID file exists and process is alive
    if not pid_file.exists():
        return False
    
    try:
        pid = int(pid_file.read_text().strip())
        # Check if process exists (signal 0 doesn't send anything, just checks)
        os.kill(pid, 0)
    except (ValueError, ProcessLookupError, PermissionError):
        return False
    
    # Also verify socket is accessible
    if not socket_path.exists():
        return False
    
    return True


def get_daemon_pid(pid_file: Path = DEFAULT_PID_FILE) -> int | None:
    """Get the daemon PID if running."""
    if not pid_file.exists():
        return None
    try:
        return int(pid_file.read_text().strip())
    except (ValueError, IOError):
        return None


class DaemonClient:
    """Client for the warm model daemon.
    
    Provides sync wrappers around async socket communication.
    
    Usage:
        client = DaemonClient()
        if client.is_connected():
            response = client.transcribe([Path("audio.wav")])
    """
    
    def __init__(
        self,
        socket_path: Path = DEFAULT_SOCKET_PATH,
        timeout: float = 300.0,  # 5 minute timeout for long transcriptions
    ) -> None:
        self.socket_path = socket_path
        self.timeout = timeout
    
    async def _send_request(self, request_json: str) -> str:
        """Send a request and receive response via Unix socket."""
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(str(self.socket_path)),
            timeout=5.0,  # Connection timeout
        )
        
        try:
            # Send request (newline-delimited)
            writer.write((request_json + "\n").encode("utf-8"))
            await writer.drain()
            
            # Read response
            response_data = await asyncio.wait_for(
                reader.readline(),
                timeout=self.timeout,
            )
            return response_data.decode("utf-8").strip()
        finally:
            writer.close()
            await writer.wait_closed()
    
    def _run_async(self, coro: object) -> object:
        """Run an async coroutine synchronously."""
        return asyncio.run(coro)
    
    def is_connected(self) -> bool:
        """Check if we can connect to the daemon."""
        if not self.socket_path.exists():
            return False
        try:
            status = self.status()
            return status.running
        except Exception:
            return False
    
    def status(self) -> StatusResponse:
        """Get daemon status."""
        request = StatusRequest()
        response_json = self._run_async(self._send_request(request.to_json()))
        return StatusResponse.from_json(response_json)
    
    def transcribe(
        self,
        audio_paths: list[Path],
        language: str = "en",
        max_new_tokens: int = 256,
    ) -> list["TranscriptSegment"]:
        """Transcribe audio files via the daemon.
        
        Returns list of TranscriptSegment objects.
        Raises RuntimeError if transcription fails.
        """
        from vociferous.domain.model import TranscriptSegment
        
        request = TranscribeRequest(
            audio_paths=[str(p) for p in audio_paths],
            language=language,
            max_new_tokens=max_new_tokens,
        )
        
        response_json = self._run_async(self._send_request(request.to_json()))
        response = TranscribeResponse.from_json(response_json)
        
        if not response.success:
            raise RuntimeError(f"Daemon transcription failed: {response.error}")
        
        # Convert dicts back to TranscriptSegment objects
        segments = []
        for seg_dict in response.segments:
            segments.append(TranscriptSegment(
                id=seg_dict["id"],
                start=seg_dict["start"],
                end=seg_dict["end"],
                raw_text=seg_dict["raw_text"],
                refined_text=seg_dict.get("refined_text"),
            ))
        
        return segments
    
    def shutdown(self) -> ShutdownResponse:
        """Request daemon shutdown."""
        request = ShutdownRequest()
        response_json = self._run_async(self._send_request(request.to_json()))
        return ShutdownResponse.from_json(response_json)


def transcribe_via_daemon(
    audio_paths: list[Path],
    language: str = "en",
    max_new_tokens: int = 256,
    socket_path: Path = DEFAULT_SOCKET_PATH,
) -> list["TranscriptSegment"] | None:
    """Convenience function to transcribe via daemon if available.
    
    Returns None if daemon is not running (caller should fallback to direct).
    """
    if not is_daemon_running(socket_path=socket_path):
        return None
    
    try:
        client = DaemonClient(socket_path=socket_path)
        return client.transcribe(
            audio_paths=audio_paths,
            language=language,
            max_new_tokens=max_new_tokens,
        )
    except Exception:
        return None
