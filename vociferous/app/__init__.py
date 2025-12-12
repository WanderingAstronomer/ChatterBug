"""Application-layer orchestration.

NOTE: Third-party logging suppression (NeMo, Transformers, HuggingFace, etc.)
is handled at the CLI entry point (cli/main.py) via environment variables
set BEFORE imports. This is required because NeMo uses a custom logging
system that ignores Python's logging.setLevel().
"""

import logging

import structlog

from .batch import (
    BatchResult,
    BatchStats,
    BatchTranscriptionRunner,
    compute_batch_stats,
    generate_combined_transcript,
)
from .progress import (
    NullProgressTracker,
    ProgressTracker,
    RichProgressTracker,
    SimpleProgressTracker,
    TranscriptionProgress,
    transcription_progress,
)
from .workflow import transcribe_file_workflow, transcribe_workflow


def configure_logging() -> None:
    """Configure structlog for application logging.
    
    Third-party logging suppression is handled at CLI entry point.
    See cli/main.py for environment variable setup.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

__all__ = [
    "BatchResult",
    "BatchStats",
    "BatchTranscriptionRunner",
    "NullProgressTracker",
    "ProgressTracker",
    "RichProgressTracker",
    "SimpleProgressTracker",
    "TranscriptionProgress",
    "compute_batch_stats",
    "configure_logging",
    "generate_combined_transcript",
    "transcribe_file_workflow",
    "transcribe_workflow",
    "transcription_progress",
]

