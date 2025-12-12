"""Application-layer orchestration."""

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
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # Silence verbose engine/VAD progress logs that write to stdout
    logging.getLogger("whisper").setLevel(logging.ERROR)
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

