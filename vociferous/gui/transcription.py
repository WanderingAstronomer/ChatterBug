"""Integration layer between GUI and Vociferous core functionality."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

import structlog

from vociferous.app import transcribe_workflow
from vociferous.config import load_config
from vociferous.domain import EngineConfig, TranscriptionOptions
from vociferous.domain.model import EngineKind
from vociferous.engines.factory import build_engine
from vociferous.engines.model_registry import normalize_model_name

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
        self.should_stop = False
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
            
            # Check if we should stop before starting
            if self.should_stop:
                return
            
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
                prompt=None,
                params={},
            )
            
            # Build engine
            engine_adapter = build_engine(self.engine, engine_config)
            keep_flag = not config.artifacts.cleanup_intermediates
            result = transcribe_workflow(
                self.file_path,
                engine_kind=self.engine,
                engine_config=engine_config,
                options=options,
                keep_intermediates=keep_flag,
                artifact_config=config.artifacts,
                engine=engine_adapter,
            )

            accumulated = []
            for segment in result.segments:
                if self.should_stop:
                    logger.info("Transcription stopped by user")
                    return
                accumulated.append(segment.text)
                self.transcript = " ".join(accumulated).strip()
                if self.on_progress:
                    self.on_progress(self.transcript)

            logger.info("Transcription complete", length=len(result.text))
            if self.on_complete:
                self.on_complete(result.text)
                
        except Exception as e:
            logger.error("Transcription error", error=str(e))
            error_msg = f"Transcription failed: {e!s}"
            if self.on_error:
                self.on_error(error_msg)
        finally:
            self.is_running = False

    def stop(self) -> None:
        """Stop the transcription task.
        
        Note: This sets a flag to stop the task. The workflow currently
        runs to completion, but callbacks halt after stop() is invoked.
        """
        logger.info("Stopping transcription task")
        self.should_stop = True
        self.is_running = False


class GUITranscriptionManager:
    """Manages transcription tasks for the GUI."""

    def __init__(self):
        """Initialize the transcription manager."""
        self.current_task: TranscriptionTask | None = None

    def transcribe(
        self,
        file_path: Path,
        engine: EngineKind = "canary_qwen",
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
