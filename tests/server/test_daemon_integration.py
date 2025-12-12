"""Integration tests for daemon lifecycle (real daemon, no mocks).

These tests start the actual daemon, make real requests, and verify
the full end-to-end flow works correctly.

IMPORTANT: These tests are marked as slow because they:
1. Start a real uvicorn server
2. Load the real Canary-Qwen model (requires GPU)
3. Perform actual transcription

Run with: pytest tests/server/test_daemon_integration.py -v --slow
Skip with: pytest tests/server/ -v -m "not slow"
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

# Test audio file
SAMPLE_AUDIO = Path(__file__).parent.parent / "audio" / "sample_audio" / "ASR_Test.wav"


def wait_for_daemon(timeout: int = 60, check_model: bool = True) -> bool:
    """Wait for daemon to be ready."""
    import requests
    
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = requests.get("http://127.0.0.1:8765/health", timeout=2)
            if response.ok:
                data = response.json()
                if not check_model or data.get("model_loaded"):
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def stop_daemon_if_running() -> None:
    """Stop daemon if it's running."""
    subprocess.run(
        [sys.executable, "-m", "vociferous", "daemon", "stop"],
        capture_output=True,
        text=True,
    )
    # Wait for shutdown
    time.sleep(2)


@pytest.fixture(scope="module")
def running_daemon():
    """Fixture that ensures daemon is running for tests.
    
    Starts daemon before tests, stops after all tests complete.
    """
    # Clean up any existing daemon
    stop_daemon_if_running()
    
    # Start daemon
    result = subprocess.run(
        [sys.executable, "-m", "vociferous", "daemon", "start", "--detach"],
        capture_output=True,
        text=True,
        timeout=120,  # Model loading can take time
    )
    
    if result.returncode != 0:
        pytest.skip(f"Failed to start daemon: {result.stderr}")
    
    # Wait for daemon to be ready with model loaded
    if not wait_for_daemon(timeout=90, check_model=True):
        stop_daemon_if_running()
        pytest.skip("Daemon failed to start within timeout")
    
    yield  # Run tests
    
    # Cleanup
    stop_daemon_if_running()


@pytest.mark.slow
class TestDaemonLifecycle:
    """Test daemon start/stop lifecycle."""

    def test_daemon_starts_and_responds_to_health(self) -> None:
        """Test that daemon can be started and responds to health checks."""
        import requests
        
        # Clean up first
        stop_daemon_if_running()
        
        try:
            # Start daemon
            subprocess.run(
                [sys.executable, "-m", "vociferous", "daemon", "start", "--detach"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            
            # Wait for startup (model loading takes time)
            assert wait_for_daemon(timeout=90), "Daemon failed to become ready"
            
            # Check health endpoint
            response = requests.get("http://127.0.0.1:8765/health", timeout=5)
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "ready"
            assert data["model_loaded"] is True
            assert "uptime_seconds" in data
            assert data["requests_handled"] >= 0
            
        finally:
            stop_daemon_if_running()

    def test_daemon_stop_gracefully(self) -> None:
        """Test that daemon can be stopped gracefully."""
        import requests
        
        # Clean up first
        stop_daemon_if_running()
        
        try:
            # Start daemon
            subprocess.run(
                [sys.executable, "-m", "vociferous", "daemon", "start", "--detach"],
                capture_output=True,
                timeout=120,
            )
            
            assert wait_for_daemon(timeout=90), "Daemon failed to start"
            
            # Stop daemon
            result = subprocess.run(
                [sys.executable, "-m", "vociferous", "daemon", "stop"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert result.returncode == 0
            
            # Verify stopped
            time.sleep(2)
            with pytest.raises(requests.exceptions.RequestException):
                requests.get("http://127.0.0.1:8765/health", timeout=2)
                
        finally:
            stop_daemon_if_running()


@pytest.mark.slow
class TestDaemonTranscription:
    """Test transcription via daemon (requires running daemon)."""

    @pytest.mark.skipif(
        not SAMPLE_AUDIO.exists(),
        reason=f"Sample audio not found: {SAMPLE_AUDIO}",
    )
    def test_transcribe_via_daemon(self, running_daemon) -> None:
        """Test transcription through daemon with real audio."""
        from vociferous.domain.model import TranscriptSegment
        from vociferous.server.client import DaemonClient
        
        client = DaemonClient()
        
        # Verify daemon is responsive
        assert client.ping(), "Daemon not responding"
        
        # Transcribe real audio
        segments = client.transcribe(SAMPLE_AUDIO)
        
        # Verify results
        assert segments is not None
        assert len(segments) > 0
        assert all(isinstance(s, TranscriptSegment) for s in segments)
        
        # Each segment should have valid content
        for segment in segments:
            assert segment.start >= 0
            assert segment.end > segment.start
            assert len(segment.raw_text.strip()) > 0

    @pytest.mark.skipif(
        not SAMPLE_AUDIO.exists(),
        reason=f"Sample audio not found: {SAMPLE_AUDIO}",
    )
    def test_batch_transcribe_via_daemon(self, running_daemon) -> None:
        """Test batch transcription through daemon."""
        from vociferous.server.client import DaemonClient
        
        client = DaemonClient()
        
        # Batch transcribe (same file twice)
        results = client.batch_transcribe([SAMPLE_AUDIO, SAMPLE_AUDIO])
        
        assert results is not None
        assert len(results) == 2
        
        # Both should have segments
        for segments in results:
            assert len(segments) > 0


@pytest.mark.slow
class TestDaemonRefinement:
    """Test refinement via daemon."""

    def test_refine_text_via_daemon(self, running_daemon) -> None:
        """Test text refinement through daemon."""
        from vociferous.server.client import DaemonClient
        
        client = DaemonClient()
        
        # Refine some text
        input_text = "hello world this is a test of the refinement"
        refined = client.refine(input_text)
        
        assert refined is not None
        assert len(refined.strip()) > 0
        # Refinement should produce reasonable output
        # (may be same as input if already clean)


@pytest.mark.slow  
class TestDaemonConvenienceFunctions:
    """Test convenience functions with real daemon."""

    @pytest.mark.skipif(
        not SAMPLE_AUDIO.exists(),
        reason=f"Sample audio not found: {SAMPLE_AUDIO}",
    )
    def test_transcribe_via_daemon_function(self, running_daemon) -> None:
        """Test transcribe_via_daemon convenience function."""
        from vociferous.server.client import transcribe_via_daemon
        
        segments = transcribe_via_daemon(SAMPLE_AUDIO)
        
        assert segments is not None
        assert len(segments) > 0

    def test_refine_via_daemon_function(self, running_daemon) -> None:
        """Test refine_via_daemon convenience function."""
        from vociferous.server.client import refine_via_daemon
        
        result = refine_via_daemon("test input text")
        
        assert result is not None


@pytest.mark.slow
class TestDaemonStatus:
    """Test daemon status reporting."""

    def test_status_shows_requests_count(self, running_daemon) -> None:
        """Test that status shows request count."""
        from vociferous.server.client import DaemonClient
        
        client = DaemonClient()
        
        # Get initial status
        status1 = client.status()
        initial_count = status1["requests_handled"]
        
        # Make a request (refine is quick)
        client.refine("test text")
        
        # Check count increased
        status2 = client.status()
        assert status2["requests_handled"] > initial_count

    def test_status_shows_uptime(self, running_daemon) -> None:
        """Test that status shows uptime."""
        from vociferous.server.client import DaemonClient
        
        client = DaemonClient()
        
        status = client.status()
        
        assert "uptime_seconds" in status
        assert status["uptime_seconds"] >= 0
