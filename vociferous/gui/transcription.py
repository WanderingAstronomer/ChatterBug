"""Integration layer between GUI and Vociferous core functionality."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Any
import threading

import structlog

from vociferous.app import TranscriptionSession
from vociferous.audio.sources import FileSource
from vociferous.config import load_config
from vociferous.domain import EngineConfig, TranscriptionOptions
from vociferous.domain.model import EngineKind, TranscriptionPreset
from vociferous.engines.factory import build_engine
from vociferous.engines.model_registry import normalize_model_name
from vociferous.domain.exceptions import (
    DependencyError, EngineError, AudioDecodeError, ConfigurationError
)

logger = structlog.get_logger(__name__)


class TranscriptionTask:
    """Represents a transcription task with progress tracking."""

    def __init__(
        self,
        file_path: Path,
        engine: EngineKind = "whisper_turbo",
        language: str = "en",
        on_progress: Callable[[str], None] | None = None,
        on_complete: Callable[[str], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ):
        """Initialize a transcription task.
        
        Args:
            file_path: Path to the audio file
            engine: Engine to use for transcription
            language: Language code
            on_progress: Callback for progress updates (receives text)
            on_complete: Callback when transcription completes (receives full text)
            on_error: Callback when error occurs (receives error message)
        """
        self.file_path = file_path
        self.engine = engine
        self.language = language
        self.on_progress = on_progress
        self.on_complete = on_complete
        self.on_error = on_error
        
        self.transcript = ""
        self.is_running = False
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the transcription task in a background thread."""
        if self.is_running:
            logger.warning("Task already running")
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._run_transcription, daemon=True)
        self.thread.start()

    def _run_transcription(self) -> None:
        """Run the transcription (called in background thread)."""
        try:
            logger.info("Starting transcription", file=str(self.file_path), engine=self.engine)
            
            # Load config
            config = load_config()
            
            # Create engine config
            engine_config = EngineConfig(
                model_name=normalize_model_name(self.engine, config.model_name),
                compute_type=config.compute_type,
                device=config.device,
                model_cache_dir=config.model_cache_dir,
                params=dict(config.params),
            )
            
            # Create transcription options
            options = TranscriptionOptions(
                language=self.language,
                preset=None,
                prompt=None,
                params={},
            )
            
            # Build engine
            engine_adapter = build_engine(self.engine, engine_config)
            
            # Create file source
            source = FileSource(self.file_path)
            
            # Create a simple sink that captures text
            class CapturingSink:
                def __init__(self, task: TranscriptionTask):
                    self.task = task
                    self.text = ""
                
                def write_segment(self, segment: Any) -> None:
                    """Capture segment text."""
                    text = segment.text if hasattr(segment, 'text') else str(segment)
                    self.text += text + " "
                    self.task.transcript = self.text.strip()
                    if self.task.on_progress:
                        self.task.on_progress(self.task.transcript)
                
                def close(self) -> None:
                    """Finalize."""
                    pass
            
            sink = CapturingSink(self)
            
            # Run transcription
            session = TranscriptionSession()
            session.start(source, engine_adapter, sink, options, engine_kind=self.engine)
            session.join()
            
            # Notify completion
            logger.info("Transcription complete", length=len(self.transcript))
            if self.on_complete:
                self.on_complete(self.transcript)
                
        except Exception as e:
            logger.error("Transcription error", error=str(e))
            error_msg = f"Transcription failed: {str(e)}"
            if self.on_error:
                self.on_error(error_msg)
        finally:
            self.is_running = False

    def stop(self) -> None:
        """Stop the transcription task."""
        self.is_running = False
        # Note: TranscriptionSession doesn't have a stop method in the current implementation
        # This would need to be added to properly support cancellation


class GUITranscriptionManager:
    """Manages transcription tasks for the GUI."""

    def __init__(self):
        """Initialize the transcription manager."""
        self.current_task: TranscriptionTask | None = None

    def transcribe(
        self,
        file_path: Path,
        engine: EngineKind = "whisper_turbo",
        language: str = "en",
        on_progress: Callable[[str], None] | None = None,
        on_complete: Callable[[str], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> TranscriptionTask:
        """Start a new transcription task.
        
        Args:
            file_path: Path to the audio file
            engine: Engine to use
            language: Language code
            on_progress: Progress callback
            on_complete: Completion callback
            on_error: Error callback
            
        Returns:
            The created transcription task
        """
        # Stop current task if running
        if self.current_task and self.current_task.is_running:
            logger.warning("Stopping current task to start new one")
            self.current_task.stop()
        
        # Create and start new task
        task = TranscriptionTask(
            file_path=file_path,
            engine=engine,
            language=language,
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error,
        )
        task.start()
        self.current_task = task
        
        return task

    def stop_current(self) -> None:
        """Stop the current transcription task."""
        if self.current_task:
            self.current_task.stop()
            self.current_task = None
