"""Tests for daemon HTTP client."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import Mock, patch


class TestDaemonClient:
    """Test DaemonClient class."""

    def test_client_initialization(self) -> None:
        """Test DaemonClient initializes with correct defaults."""
        from vociferous.server.client import (
            DaemonClient,
            DEFAULT_DAEMON_HOST,
            DEFAULT_DAEMON_PORT,
            DEFAULT_TIMEOUT_S,
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

    @patch("vociferous.server.client.requests.get")
    def test_ping_success(self, mock_get: Mock) -> None:
        """Test ping returns True when daemon is healthy."""
        from vociferous.server.client import DaemonClient
        
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"model_loaded": True}
        mock_get.return_value = mock_response
        
        client = DaemonClient()
        assert client.ping() is True

    @patch("vociferous.server.client.requests.get")
    def test_ping_model_not_loaded(self, mock_get: Mock) -> None:
        """Test ping returns False when model not loaded."""
        from vociferous.server.client import DaemonClient
        
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"model_loaded": False}
        mock_get.return_value = mock_response
        
        client = DaemonClient()
        assert client.ping() is False

    @patch("vociferous.server.client.requests.get")
    def test_ping_connection_error(self, mock_get: Mock) -> None:
        """Test ping returns False on connection error."""
        from vociferous.server.client import DaemonClient
        from requests.exceptions import ConnectionError
        
        mock_get.side_effect = ConnectionError()
        
        client = DaemonClient()
        assert client.ping() is False

    @patch("vociferous.server.client.requests.get")
    def test_status_success(self, mock_get: Mock) -> None:
        """Test status returns daemon info."""
        from vociferous.server.client import DaemonClient
        
        status_data = {
            "status": "ready",
            "model_loaded": True,
            "model_name": "nvidia/canary-qwen-2.5b",
            "uptime_seconds": 123.4,
            "requests_handled": 42,
        }
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = status_data
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        client = DaemonClient()
        result = client.status()
        
        assert result == status_data

    @patch("vociferous.server.client.requests.get")
    def test_status_connection_error(self, mock_get: Mock) -> None:
        """Test status raises DaemonNotRunningError on connection error."""
        from vociferous.server.client import DaemonClient, DaemonNotRunningError
        from requests.exceptions import ConnectionError
        
        mock_get.side_effect = ConnectionError()
        
        client = DaemonClient()
        with pytest.raises(DaemonNotRunningError):
            client.status()


class TestTranscribe:
    """Test transcribe method."""

    def test_transcribe_file_not_found(self, tmp_path: Path) -> None:
        """Test transcribe raises FileNotFoundError for missing file."""
        from vociferous.server.client import DaemonClient
        
        client = DaemonClient()
        with pytest.raises(FileNotFoundError):
            client.transcribe(tmp_path / "nonexistent.wav")

    @patch("vociferous.server.client.requests.post")
    def test_transcribe_success(self, mock_post: Mock, tmp_path: Path) -> None:
        """Test successful transcription."""
        from vociferous.server.client import DaemonClient
        
        # Create dummy audio file
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"fake audio data")
        
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "success": True,
            "segments": [
                {"start": 0.0, "end": 5.0, "text": "Hello world", "language": "en"},
            ],
            "inference_time_s": 2.1,
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        client = DaemonClient()
        segments = client.transcribe(audio_file)
        
        assert len(segments) == 1
        assert segments[0].raw_text == "Hello world"
        assert segments[0].start == 0.0
        assert segments[0].end == 5.0

    @patch("vociferous.server.client.requests.post")
    def test_transcribe_connection_error(self, mock_post: Mock, tmp_path: Path) -> None:
        """Test transcribe raises DaemonNotRunningError on connection error."""
        from vociferous.server.client import DaemonClient, DaemonNotRunningError
        from requests.exceptions import ConnectionError
        
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"fake audio data")
        
        mock_post.side_effect = ConnectionError()
        
        client = DaemonClient()
        with pytest.raises(DaemonNotRunningError):
            client.transcribe(audio_file)

    @patch("vociferous.server.client.requests.post")
    def test_transcribe_timeout(self, mock_post: Mock, tmp_path: Path) -> None:
        """Test transcribe raises DaemonTimeoutError on timeout."""
        from vociferous.server.client import DaemonClient, DaemonTimeoutError
        from requests.exceptions import Timeout
        
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"fake audio data")
        
        mock_post.side_effect = Timeout()
        
        client = DaemonClient(timeout=1.0)
        with pytest.raises(DaemonTimeoutError):
            client.transcribe(audio_file)


class TestRefine:
    """Test refine method."""

    @patch("vociferous.server.client.requests.post")
    def test_refine_success(self, mock_post: Mock) -> None:
        """Test successful refinement."""
        from vociferous.server.client import DaemonClient
        
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "success": True,
            "refined_text": "Refined transcript text.",
            "inference_time_s": 0.8,
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        client = DaemonClient()
        result = client.refine("raw transcript text")
        
        assert result == "Refined transcript text."

    @patch("vociferous.server.client.requests.post")
    def test_refine_with_instructions(self, mock_post: Mock) -> None:
        """Test refinement with custom instructions."""
        from vociferous.server.client import DaemonClient
        
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "success": True,
            "refined_text": "Formal refined text.",
            "inference_time_s": 0.9,
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        client = DaemonClient()
        result = client.refine("raw text", instructions="Make it formal")
        
        assert result == "Formal refined text."
        
        # Verify instructions were sent
        call_args = mock_post.call_args
        assert call_args[1]["json"]["instructions"] == "Make it formal"


class TestBatchTranscribe:
    """Test batch_transcribe method."""

    def test_batch_transcribe_file_not_found(self, tmp_path: Path) -> None:
        """Test batch_transcribe raises FileNotFoundError for missing file."""
        from vociferous.server.client import DaemonClient
        
        existing = tmp_path / "existing.wav"
        existing.write_bytes(b"audio")
        missing = tmp_path / "missing.wav"
        
        client = DaemonClient()
        with pytest.raises(FileNotFoundError):
            client.batch_transcribe([existing, missing])

    @patch("vociferous.server.client.requests.post")
    def test_batch_transcribe_success(self, mock_post: Mock, tmp_path: Path) -> None:
        """Test successful batch transcription."""
        from vociferous.server.client import DaemonClient
        
        # Create dummy audio files
        audio1 = tmp_path / "audio1.wav"
        audio1.write_bytes(b"audio data 1")
        audio2 = tmp_path / "audio2.wav"
        audio2.write_bytes(b"audio data 2")
        
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "success": True,
            "results": [
                {
                    "segments": [{"start": 0.0, "end": 5.0, "text": "First", "language": "en"}],
                    "inference_time_s": 1.0,
                },
                {
                    "segments": [{"start": 0.0, "end": 3.0, "text": "Second", "language": "en"}],
                    "inference_time_s": 0.8,
                },
            ],
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        client = DaemonClient()
        results = client.batch_transcribe([audio1, audio2])
        
        assert len(results) == 2
        assert results[0][0].raw_text == "First"
        assert results[1][0].raw_text == "Second"


class TestConvenienceFunctions:
    """Test convenience functions for workflow integration."""

    @patch("vociferous.server.client.DaemonClient.transcribe")
    def test_transcribe_via_daemon_success(self, mock_transcribe: Mock, tmp_path: Path) -> None:
        """Test transcribe_via_daemon returns segments on success."""
        from vociferous.server.client import transcribe_via_daemon
        from vociferous.domain.model import TranscriptSegment
        
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"audio")
        
        mock_segment = TranscriptSegment(start=0.0, end=5.0, raw_text="Test")
        mock_transcribe.return_value = [mock_segment]
        
        result = transcribe_via_daemon(audio_file)
        
        assert result is not None
        assert len(result) == 1

    @patch("vociferous.server.client.DaemonClient.transcribe")
    def test_transcribe_via_daemon_not_running(self, mock_transcribe: Mock, tmp_path: Path) -> None:
        """Test transcribe_via_daemon returns None if daemon not running."""
        from vociferous.server.client import transcribe_via_daemon, DaemonNotRunningError
        
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"audio")
        
        mock_transcribe.side_effect = DaemonNotRunningError()
        
        result = transcribe_via_daemon(audio_file)
        
        assert result is None

    @patch("vociferous.server.client.DaemonClient.refine")
    def test_refine_via_daemon_success(self, mock_refine: Mock) -> None:
        """Test refine_via_daemon returns refined text on success."""
        from vociferous.server.client import refine_via_daemon
        
        mock_refine.return_value = "Refined text"
        
        result = refine_via_daemon("raw text")
        
        assert result == "Refined text"

    @patch("vociferous.server.client.DaemonClient.refine")
    def test_refine_via_daemon_not_running(self, mock_refine: Mock) -> None:
        """Test refine_via_daemon returns None if daemon not running."""
        from vociferous.server.client import refine_via_daemon, DaemonNotRunningError
        
        mock_refine.side_effect = DaemonNotRunningError()
        
        result = refine_via_daemon("raw text")
        
        assert result is None


class TestHelperFunctions:
    """Test module-level helper functions."""

    @patch("vociferous.server.client.requests.get")
    def test_is_daemon_running_true(self, mock_get: Mock) -> None:
        """Test is_daemon_running returns True when daemon is healthy."""
        from vociferous.server.client import is_daemon_running
        
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"model_loaded": True}
        mock_get.return_value = mock_response
        
        assert is_daemon_running() is True

    @patch("vociferous.server.client.requests.get")
    def test_is_daemon_running_false(self, mock_get: Mock) -> None:
        """Test is_daemon_running returns False on connection error."""
        from vociferous.server.client import is_daemon_running
        from requests.exceptions import ConnectionError
        
        mock_get.side_effect = ConnectionError()
        
        assert is_daemon_running() is False

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

    def test_get_daemon_pid_stale_pid(self, tmp_path: Path) -> None:
        """Test get_daemon_pid returns None for stale PID."""
        from vociferous.server.client import get_daemon_pid
        
        pid_file = tmp_path / "daemon.pid"
        pid_file.write_text("999999999")  # PID that definitely doesn't exist
        
        result = get_daemon_pid(pid_file=pid_file)
        
        assert result is None
