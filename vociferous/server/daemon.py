"""Warm model daemon server.

Keeps Canary-Qwen loaded in GPU memory for fast inference.
Communicates via Unix domain socket.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket
import time
from dataclasses import dataclass, asdict
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
    parse_request,
)

if TYPE_CHECKING:
    from vociferous.engines.canary_qwen import CanaryQwenEngine

logger = logging.getLogger(__name__)


@dataclass
class DaemonState:
    """Mutable daemon state."""
    
    start_time: float = 0.0
    requests_served: int = 0
    running: bool = True


class WarmModelDaemon:
    """Daemon server that keeps the model warm in GPU memory.
    
    Usage:
        daemon = WarmModelDaemon()
        await daemon.start()  # Blocks until shutdown
    """
    
    def __init__(
        self,
        socket_path: Path = DEFAULT_SOCKET_PATH,
        pid_file: Path = DEFAULT_PID_FILE,
        model_name: str = "nvidia/canary-qwen-2.5b",
    ) -> None:
        self.socket_path = socket_path
        self.pid_file = pid_file
        self.model_name = model_name
        self.state = DaemonState()
        self._engine: CanaryQwenEngine | None = None
        self._server: asyncio.Server | None = None
    
    def _load_model(self) -> None:
        """Load the Canary-Qwen model into GPU memory."""
        from vociferous.engines.canary_qwen import CanaryQwenEngine
        from vociferous.domain.model import EngineConfig
        
        logger.info("Loading model: %s", self.model_name)
        start = time.perf_counter()
        
        # Create engine config with the model name
        config = EngineConfig(
            model_name=self.model_name,
            device="auto",
            compute_type="fp16",
        )
        
        self._engine = CanaryQwenEngine(config)
        # Model is loaded lazily in __init__, so it's already ready
        
        elapsed = time.perf_counter() - start
        logger.info("Model loaded in %.2fs", elapsed)
    
    def _get_device(self) -> str:
        """Get the device the model is loaded on."""
        if self._engine is None:
            return "not loaded"
        try:
            model = self._engine._lazy_model()
            # Try to get device from model parameters
            for param in model.parameters():
                return str(param.device)
            return "unknown"
        except Exception:
            return "unknown"
    
    async def _handle_transcribe(self, request: TranscribeRequest) -> TranscribeResponse:
        """Handle a transcription request."""
        if self._engine is None:
            return TranscribeResponse(
                segments=[],
                success=False,
                error="Model not loaded",
                request_id=request.request_id,
            )
        
        try:
            from vociferous.domain.model import TranscriptionOptions
            
            start = time.perf_counter()
            
            # Convert string paths to Path objects
            audio_paths = [Path(p) for p in request.audio_paths]
            
            # Create options object from request parameters
            options = TranscriptionOptions(
                language=request.language,
                max_new_tokens=request.max_new_tokens,
            )
            
            # Use batch transcription for efficiency
            all_results = self._engine.transcribe_files_batch(
                audio_paths=audio_paths,
                options=options,
            )
            
            # Flatten results (batch returns list of lists)
            segments = []
            for file_segments in all_results:
                segments.extend(file_segments)
            
            elapsed_ms = (time.perf_counter() - start) * 1000
            
            # Convert segments to dicts for JSON serialization
            segment_dicts = [asdict(s) for s in segments]
            
            self.state.requests_served += 1
            
            return TranscribeResponse(
                segments=segment_dicts,
                success=True,
                request_id=request.request_id,
                inference_time_ms=elapsed_ms,
            )
            
        except Exception as e:
            logger.exception("Transcription failed")
            return TranscribeResponse(
                segments=[],
                success=False,
                error=str(e),
                request_id=request.request_id,
            )
    
    def _handle_status(self) -> StatusResponse:
        """Handle a status request."""
        uptime = time.time() - self.state.start_time if self.state.start_time else 0
        return StatusResponse(
            running=self.state.running,
            model_loaded=self._engine is not None,
            model_name=self.model_name,
            device=self._get_device(),
            uptime_seconds=uptime,
            requests_served=self.state.requests_served,
        )
    
    async def _handle_shutdown(self) -> ShutdownResponse:
        """Handle a shutdown request."""
        logger.info("Shutdown requested")
        self.state.running = False
        return ShutdownResponse(success=True, message="Shutting down")
    
    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle a single client connection."""
        try:
            # Read request (newline-delimited JSON)
            data = await reader.readline()
            if not data:
                return
            
            request_str = data.decode("utf-8").strip()
            logger.debug("Received: %s", request_str[:100])
            
            try:
                request = parse_request(request_str)
            except Exception as e:
                response = TranscribeResponse(
                    segments=[],
                    success=False,
                    error=f"Invalid request: {e}",
                )
                writer.write((response.to_json() + "\n").encode("utf-8"))
                await writer.drain()
                return
            
            # Dispatch to handler
            if isinstance(request, TranscribeRequest):
                response = await self._handle_transcribe(request)
            elif isinstance(request, StatusRequest):
                response = self._handle_status()
            elif isinstance(request, ShutdownRequest):
                response = await self._handle_shutdown()
            else:
                response = TranscribeResponse(
                    segments=[],
                    success=False,
                    error=f"Unknown request type",
                )
            
            # Send response
            writer.write((response.to_json() + "\n").encode("utf-8"))
            await writer.drain()
            
        except Exception as e:
            logger.exception("Error handling client")
        finally:
            writer.close()
            await writer.wait_closed()
    
    def _write_pid_file(self) -> None:
        """Write current PID to file."""
        self.pid_file.write_text(str(os.getpid()))
    
    def _remove_pid_file(self) -> None:
        """Remove PID file."""
        try:
            self.pid_file.unlink(missing_ok=True)
        except Exception:
            pass
    
    def _remove_socket(self) -> None:
        """Remove socket file if it exists."""
        try:
            self.socket_path.unlink(missing_ok=True)
        except Exception:
            pass
    
    async def start(self) -> None:
        """Start the daemon server.
        
        This method blocks until shutdown is requested.
        """
        # Clean up any stale socket
        self._remove_socket()
        
        # Load the model first (this is the expensive part)
        self._load_model()
        
        # Start listening
        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=str(self.socket_path),
        )
        
        # Make socket accessible
        os.chmod(self.socket_path, 0o600)
        
        # Write PID file
        self._write_pid_file()
        
        self.state.start_time = time.time()
        self.state.running = True
        
        logger.info("Daemon started on %s (PID: %d)", self.socket_path, os.getpid())
        
        try:
            while self.state.running:
                await asyncio.sleep(0.1)
        finally:
            self._server.close()
            await self._server.wait_closed()
            self._remove_socket()
            self._remove_pid_file()
            logger.info("Daemon stopped")
    
    def stop(self) -> None:
        """Signal the daemon to stop."""
        self.state.running = False


def run_daemon(
    socket_path: Path = DEFAULT_SOCKET_PATH,
    pid_file: Path = DEFAULT_PID_FILE,
    model_name: str = "nvidia/canary-qwen-2.5b",
) -> None:
    """Run the warm model daemon (blocking).
    
    This is the main entry point for running the daemon.
    Sets up signal handlers and runs the async event loop.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    
    daemon = WarmModelDaemon(
        socket_path=socket_path,
        pid_file=pid_file,
        model_name=model_name,
    )
    
    # Handle graceful shutdown
    def handle_signal(signum: int, frame: object) -> None:
        logger.info("Received signal %d, shutting down", signum)
        daemon.stop()
    
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    
    # Run the daemon
    asyncio.run(daemon.start())


if __name__ == "__main__":
    run_daemon()
