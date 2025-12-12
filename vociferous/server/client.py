"""HTTP client for Vociferous daemon server.

Provides a simple interface for communicating with the warm model daemon
via HTTP, with proper error handling and convenient fallback functions.

Usage:
    from vociferous.server.client import DaemonClient, transcribe_via_daemon
    
    # Check if daemon is running
    client = DaemonClient()
    if client.ping():
        segments = client.transcribe(Path("audio.wav"))
    
    # Or use convenience function (returns None if daemon unavailable)
    segments = transcribe_via_daemon(Path("audio.wav"))
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import requests
from requests.exceptions import ConnectionError, RequestException, Timeout

from vociferous.domain.model import TranscriptSegment
from vociferous.domain.exceptions import VociferousError

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Default daemon configuration
DEFAULT_DAEMON_HOST = "127.0.0.1"
DEFAULT_DAEMON_PORT = 8765
DEFAULT_TIMEOUT_S = 60.0

# Cache directory for PID file
CACHE_DIR = Path.home() / ".cache" / "vociferous"
PID_FILE = CACHE_DIR / "daemon.pid"


# ============================================================================
# Exceptions
# ============================================================================


class DaemonError(VociferousError):
    """Base exception for daemon communication errors."""

    pass


class DaemonNotRunningError(DaemonError):
    """Daemon is not running or unreachable."""

    pass


class DaemonTimeoutError(DaemonError):
    """Daemon request timed out."""

    pass


# ============================================================================
# Helper Functions
# ============================================================================


def is_daemon_running(
    host: str = DEFAULT_DAEMON_HOST,
    port: int = DEFAULT_DAEMON_PORT,
) -> bool:
    """Check if daemon is running by pinging health endpoint.

    Args:
        host: Daemon host address
        port: Daemon port number

    Returns:
        True if daemon is running and model is loaded
    """
    try:
        response = requests.get(
            f"http://{host}:{port}/health",
            timeout=2.0,
        )
        if response.ok:
            data = response.json()
            return data.get("model_loaded", False)
        return False
    except RequestException:
        return False


def get_daemon_pid(pid_file: Path = PID_FILE) -> int | None:
    """Read daemon PID from PID file.

    Args:
        pid_file: Path to PID file

    Returns:
        PID if valid and process exists, None otherwise
    """
    if not pid_file.exists():
        return None

    try:
        pid = int(pid_file.read_text().strip())
        # Check if process is actually running
        os.kill(pid, 0)  # Signal 0 just checks if process exists
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        # PID file is stale or invalid
        return None


# ============================================================================
# Daemon Client
# ============================================================================


class DaemonClient:
    """HTTP client for communicating with warm model daemon.

    Provides methods for transcription, refinement, and health checks
    with proper error handling and timeout management.

    Args:
        host: Daemon host address (default: 127.0.0.1)
        port: Daemon port number (default: 8765)
        timeout: Request timeout in seconds (default: 60.0)

    Example:
        client = DaemonClient()
        if client.ping():
            segments = client.transcribe(Path("audio.wav"))
            refined = client.refine("raw transcript text")
    """

    def __init__(
        self,
        host: str = DEFAULT_DAEMON_HOST,
        port: int = DEFAULT_DAEMON_PORT,
        timeout: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        self.base_url = f"http://{host}:{port}"
        self.timeout = timeout

    def ping(self) -> bool:
        """Check if daemon is running and healthy.

        Returns:
            True if daemon is running and model is loaded
        """
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=2.0,
            )
            if response.ok:
                data = response.json()
                return data.get("model_loaded", False)
            return False
        except RequestException:
            return False

    def status(self) -> dict[str, Any]:
        """Get detailed daemon status.

        Returns:
            Dict with status, model_name, uptime_seconds, requests_handled

        Raises:
            DaemonNotRunningError: If daemon is not running
        """
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=2.0,
            )
            response.raise_for_status()
            return response.json()
        except ConnectionError as e:
            raise DaemonNotRunningError("Cannot connect to daemon. Is it running?") from e
        except RequestException as e:
            raise DaemonError(f"Failed to get daemon status: {e}") from e

    def transcribe(
        self,
        audio_path: Path,
        language: str = "en",
    ) -> list[TranscriptSegment]:
        """Transcribe audio file via daemon.

        Args:
            audio_path: Path to audio file
            language: Language code for transcription

        Returns:
            List of TranscriptSegment objects

        Raises:
            FileNotFoundError: If audio file doesn't exist
            DaemonNotRunningError: If daemon is not running
            DaemonTimeoutError: If request times out
            DaemonError: For other daemon errors
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        try:
            with open(audio_path, "rb") as f:
                response = requests.post(
                    f"{self.base_url}/transcribe",
                    files={"audio": (audio_path.name, f, "audio/wav")},
                    timeout=self.timeout,
                )

            response.raise_for_status()
            data = response.json()

            if not data.get("success"):
                raise DaemonError("Daemon returned success=false")

            # Convert to TranscriptSegment objects
            segments = []
            for seg_data in data["segments"]:
                segments.append(
                    TranscriptSegment(
                        start=seg_data["start"],
                        end=seg_data["end"],
                        raw_text=seg_data["text"],
                        language=seg_data.get("language"),
                    )
                )

            return segments

        except Timeout as e:
            raise DaemonTimeoutError(
                f"Daemon request timed out after {self.timeout}s"
            ) from e

        except ConnectionError as e:
            raise DaemonNotRunningError(
                "Cannot connect to daemon. Is it running?"
            ) from e

        except RequestException as e:
            raise DaemonError(f"Daemon request failed: {e}") from e

    def refine(
        self,
        text: str,
        instructions: str | None = None,
    ) -> str:
        """Refine text via daemon.

        Args:
            text: Raw transcript text to refine
            instructions: Optional custom refinement instructions

        Returns:
            Refined text string

        Raises:
            DaemonNotRunningError: If daemon is not running
            DaemonTimeoutError: If request times out
            DaemonError: For other daemon errors
        """
        try:
            response = requests.post(
                f"{self.base_url}/refine",
                json={"text": text, "instructions": instructions},
                timeout=30.0,  # Refinement is typically faster
            )

            response.raise_for_status()
            data = response.json()

            if not data.get("success"):
                raise DaemonError("Daemon refinement failed")

            return data["refined_text"]

        except Timeout as e:
            raise DaemonTimeoutError("Daemon refinement timed out") from e

        except ConnectionError as e:
            raise DaemonNotRunningError("Cannot connect to daemon") from e

        except RequestException as e:
            raise DaemonError(f"Daemon refinement failed: {e}") from e

    def batch_transcribe(
        self,
        audio_paths: list[Path],
        language: str = "en",
    ) -> list[list[TranscriptSegment]]:
        """Transcribe multiple files via daemon in batch.

        Args:
            audio_paths: List of paths to audio files
            language: Language code for transcription

        Returns:
            List of segment lists, one per audio file

        Raises:
            FileNotFoundError: If any audio file doesn't exist
            DaemonNotRunningError: If daemon is not running
            DaemonTimeoutError: If request times out
            DaemonError: For other daemon errors
        """
        # Validate all paths exist
        for p in audio_paths:
            if not p.exists():
                raise FileNotFoundError(f"Audio file not found: {p}")

        try:
            response = requests.post(
                f"{self.base_url}/batch-transcribe",
                json={
                    "audio_paths": [str(p) for p in audio_paths],
                    "language": language,
                },
                # Scale timeout with batch size
                timeout=self.timeout * len(audio_paths),
            )

            response.raise_for_status()
            data = response.json()

            if not data.get("success"):
                raise DaemonError("Daemon batch transcription failed")

            # Convert results
            all_segments: list[list[TranscriptSegment]] = []
            for result in data["results"]:
                segments = [
                    TranscriptSegment(
                        start=seg["start"],
                        end=seg["end"],
                        raw_text=seg["text"],
                        language=seg.get("language"),
                    )
                    for seg in result["segments"]
                ]
                all_segments.append(segments)

            return all_segments

        except Timeout as e:
            raise DaemonTimeoutError("Daemon batch transcription timed out") from e

        except ConnectionError as e:
            raise DaemonNotRunningError("Cannot connect to daemon") from e

        except RequestException as e:
            raise DaemonError(f"Daemon batch transcription failed: {e}") from e


# ============================================================================
# Convenience Functions for Workflow Integration
# ============================================================================


def transcribe_via_daemon(
    audio_path: Path,
    language: str = "en",
) -> list[TranscriptSegment] | None:
    """Try to transcribe via daemon, return None if unavailable.

    This is a convenience function for workflow integration that
    gracefully handles daemon unavailability.

    Args:
        audio_path: Path to audio file
        language: Language code for transcription

    Returns:
        List of TranscriptSegment objects if successful, None if daemon unavailable
    """
    try:
        client = DaemonClient()
        return client.transcribe(audio_path, language)
    except DaemonNotRunningError:
        logger.debug("Daemon not running, will use direct engine")
        return None
    except DaemonError as e:
        logger.warning(f"Daemon error: {e}, falling back to direct engine")
        return None


def refine_via_daemon(
    text: str,
    instructions: str | None = None,
) -> str | None:
    """Try to refine via daemon, return None if unavailable.

    Args:
        text: Raw transcript text to refine
        instructions: Optional custom refinement instructions

    Returns:
        Refined text if successful, None if daemon unavailable
    """
    try:
        client = DaemonClient()
        return client.refine(text, instructions)
    except DaemonNotRunningError:
        logger.debug("Daemon not running, will use direct engine")
        return None
    except DaemonError as e:
        logger.warning(f"Daemon refinement error: {e}, falling back")
        return None


def batch_transcribe_via_daemon(
    audio_paths: list[Path],
    language: str = "en",
) -> list[list[TranscriptSegment]] | None:
    """Try batch transcription via daemon, return None if unavailable.

    Args:
        audio_paths: List of paths to audio files
        language: Language code for transcription

    Returns:
        List of segment lists if successful, None if daemon unavailable
    """
    try:
        client = DaemonClient()
        return client.batch_transcribe(audio_paths, language)
    except DaemonNotRunningError:
        logger.debug("Daemon not running, will use direct engine")
        return None
    except DaemonError as e:
        logger.warning(f"Daemon batch error: {e}, falling back")
        return None
