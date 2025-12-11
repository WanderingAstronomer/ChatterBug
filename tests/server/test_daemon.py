"""Tests for the warm model daemon server module."""

from __future__ import annotations

import pytest
from pathlib import Path

from vociferous.server.protocol import (
    TranscribeRequest,
    TranscribeResponse,
    StatusRequest,
    StatusResponse,
    ShutdownRequest,
    ShutdownResponse,
    parse_request,
    DEFAULT_SOCKET_PATH,
    DEFAULT_PID_FILE,
)
from vociferous.server.client import is_daemon_running, get_daemon_pid


class TestProtocol:
    """Test protocol serialization/deserialization."""
    
    def test_transcribe_request_to_json(self) -> None:
        request = TranscribeRequest(
            audio_paths=["/path/to/audio.wav"],
            language="en",
            max_new_tokens=256,
            request_id="test-123",
        )
        json_str = request.to_json()
        assert '"type": "transcribe"' in json_str
        assert '"/path/to/audio.wav"' in json_str
        assert '"language": "en"' in json_str
    
    def test_transcribe_request_from_dict(self) -> None:
        data = {
            "type": "transcribe",
            "audio_paths": ["/audio1.wav", "/audio2.wav"],
            "language": "es",
            "max_new_tokens": 512,
            "request_id": "req-456",
        }
        request = TranscribeRequest.from_dict(data)
        assert request.audio_paths == ["/audio1.wav", "/audio2.wav"]
        assert request.language == "es"
        assert request.max_new_tokens == 512
        assert request.request_id == "req-456"
    
    def test_transcribe_response_roundtrip(self) -> None:
        original = TranscribeResponse(
            segments=[{"id": "1", "start": 0.0, "end": 1.0, "raw_text": "Hello"}],
            success=True,
            error=None,
            request_id="test-123",
            inference_time_ms=150.5,
        )
        json_str = original.to_json()
        restored = TranscribeResponse.from_json(json_str)
        
        assert restored.segments == original.segments
        assert restored.success == original.success
        assert restored.request_id == original.request_id
        assert restored.inference_time_ms == original.inference_time_ms
    
    def test_status_request_to_json(self) -> None:
        request = StatusRequest()
        json_str = request.to_json()
        assert '"type": "status"' in json_str
    
    def test_status_response_roundtrip(self) -> None:
        original = StatusResponse(
            running=True,
            model_loaded=True,
            model_name="nvidia/canary-qwen-2.5b",
            device="cuda:0",
            uptime_seconds=3600.0,
            requests_served=42,
        )
        json_str = original.to_json()
        restored = StatusResponse.from_json(json_str)
        
        assert restored.running == original.running
        assert restored.model_loaded == original.model_loaded
        assert restored.model_name == original.model_name
        assert restored.device == original.device
        assert restored.uptime_seconds == original.uptime_seconds
        assert restored.requests_served == original.requests_served
    
    def test_shutdown_request_to_json(self) -> None:
        request = ShutdownRequest()
        json_str = request.to_json()
        assert '"type": "shutdown"' in json_str
    
    def test_shutdown_response_roundtrip(self) -> None:
        original = ShutdownResponse(success=True, message="Shutting down gracefully")
        json_str = original.to_json()
        restored = ShutdownResponse.from_json(json_str)
        
        assert restored.success == original.success
        assert restored.message == original.message
    
    def test_parse_request_transcribe(self) -> None:
        json_str = '{"type": "transcribe", "audio_paths": ["/audio.wav"], "language": "en"}'
        request = parse_request(json_str)
        assert isinstance(request, TranscribeRequest)
        assert request.audio_paths == ["/audio.wav"]
    
    def test_parse_request_status(self) -> None:
        json_str = '{"type": "status"}'
        request = parse_request(json_str)
        assert isinstance(request, StatusRequest)
    
    def test_parse_request_shutdown(self) -> None:
        json_str = '{"type": "shutdown"}'
        request = parse_request(json_str)
        assert isinstance(request, ShutdownRequest)
    
    def test_parse_request_unknown_type(self) -> None:
        json_str = '{"type": "unknown"}'
        with pytest.raises(ValueError, match="Unknown request type"):
            parse_request(json_str)


class TestDaemonDetection:
    """Test daemon running detection."""
    
    def test_daemon_not_running_no_pid_file(self, tmp_path: Path) -> None:
        """Daemon should be detected as not running if PID file doesn't exist."""
        socket_path = tmp_path / "test.sock"
        pid_file = tmp_path / "test.pid"
        
        assert not is_daemon_running(socket_path=socket_path, pid_file=pid_file)
    
    def test_daemon_not_running_stale_pid(self, tmp_path: Path) -> None:
        """Daemon should be detected as not running if PID is stale."""
        socket_path = tmp_path / "test.sock"
        pid_file = tmp_path / "test.pid"
        
        # Write a PID that definitely doesn't exist
        pid_file.write_text("999999999")
        
        assert not is_daemon_running(socket_path=socket_path, pid_file=pid_file)
    
    def test_get_daemon_pid_no_file(self, tmp_path: Path) -> None:
        """get_daemon_pid should return None if PID file doesn't exist."""
        pid_file = tmp_path / "nonexistent.pid"
        assert get_daemon_pid(pid_file=pid_file) is None
    
    def test_get_daemon_pid_with_file(self, tmp_path: Path) -> None:
        """get_daemon_pid should return the PID from file."""
        pid_file = tmp_path / "test.pid"
        pid_file.write_text("12345")
        assert get_daemon_pid(pid_file=pid_file) == 12345


class TestDefaultPaths:
    """Test default socket and PID file paths."""
    
    def test_default_socket_path(self) -> None:
        assert DEFAULT_SOCKET_PATH == Path("/tmp/vociferous-daemon.sock")
    
    def test_default_pid_file(self) -> None:
        assert DEFAULT_PID_FILE == Path("/tmp/vociferous-daemon.pid")
