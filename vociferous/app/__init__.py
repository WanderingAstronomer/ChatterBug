"""Application-layer orchestration."""

import logging
import structlog

from .transcription_session import TranscriptionSession, SessionConfig  # noqa: F401
from .arbiter import SegmentArbiter  # noqa: F401

def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # Silence verbose engine/VAD progress logs that write to stdout
    logging.getLogger("faster_whisper").setLevel(logging.ERROR)
    logging.getLogger("faster_whisper.transcribe").setLevel(logging.ERROR)
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
    "TranscriptionSession",
    "SessionConfig",
    "SegmentArbiter",
    "configure_logging",
]

