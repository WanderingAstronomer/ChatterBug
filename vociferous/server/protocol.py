"""Protocol definitions for daemon IPC.

Uses JSON over Unix domain socket for simple, fast local IPC.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


# Default socket path (in user's runtime directory)
DEFAULT_SOCKET_PATH = Path("/tmp/vociferous-daemon.sock")
DEFAULT_PID_FILE = Path("/tmp/vociferous-daemon.pid")


@dataclass
class TranscribeRequest:
    """Request to transcribe audio files."""
    
    audio_paths: list[str]
    language: str = "en"
    max_new_tokens: int = 256
    request_id: str = ""
    
    def to_json(self) -> str:
        return json.dumps({"type": "transcribe", **asdict(self)})
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TranscribeRequest:
        return cls(
            audio_paths=data["audio_paths"],
            language=data.get("language", "en"),
            max_new_tokens=data.get("max_new_tokens", 256),
            request_id=data.get("request_id", ""),
        )


@dataclass
class TranscribeResponse:
    """Response containing transcription results."""
    
    segments: list[dict[str, Any]]  # List of segment dicts
    success: bool = True
    error: str | None = None
    request_id: str = ""
    inference_time_ms: float = 0.0
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @classmethod
    def from_json(cls, data: str) -> TranscribeResponse:
        d = json.loads(data)
        return cls(
            segments=d.get("segments", []),
            success=d.get("success", True),
            error=d.get("error"),
            request_id=d.get("request_id", ""),
            inference_time_ms=d.get("inference_time_ms", 0.0),
        )


@dataclass
class StatusRequest:
    """Request daemon status."""
    
    def to_json(self) -> str:
        return json.dumps({"type": "status"})


@dataclass
class StatusResponse:
    """Daemon status response."""
    
    running: bool = True
    model_loaded: bool = False
    model_name: str = ""
    device: str = ""
    uptime_seconds: float = 0.0
    requests_served: int = 0
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @classmethod
    def from_json(cls, data: str) -> StatusResponse:
        d = json.loads(data)
        return cls(**d)


@dataclass
class ShutdownRequest:
    """Request daemon shutdown."""
    
    def to_json(self) -> str:
        return json.dumps({"type": "shutdown"})


@dataclass 
class ShutdownResponse:
    """Shutdown acknowledgment."""
    
    success: bool = True
    message: str = "Shutting down"
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @classmethod
    def from_json(cls, data: str) -> ShutdownResponse:
        d = json.loads(data)
        return cls(**d)


def parse_request(data: str) -> TranscribeRequest | StatusRequest | ShutdownRequest:
    """Parse incoming request from JSON."""
    d = json.loads(data)
    req_type = d.get("type", "")
    
    if req_type == "transcribe":
        return TranscribeRequest.from_dict(d)
    elif req_type == "status":
        return StatusRequest()
    elif req_type == "shutdown":
        return ShutdownRequest()
    else:
        raise ValueError(f"Unknown request type: {req_type}")
