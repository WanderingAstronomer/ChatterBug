"""FastAPI server for warm Canary-Qwen model inference.

Provides HTTP endpoints for transcription and refinement with a model
kept warm in GPU memory to eliminate cold-start overhead.

Usage:
    # Start server directly (for development)
    uvicorn vociferous.server.api:app --host 127.0.0.1 --port 8765
    
    # Start via CLI (recommended)
    vociferous daemon start
"""

from __future__ import annotations

import logging
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from vociferous.domain.model import EngineConfig, TranscriptSegment

logger = logging.getLogger(__name__)

# Global state
_model: Any | None = None
_model_loaded_at: float | None = None
_requests_handled: int = 0
_model_name: str = "nvidia/canary-qwen-2.5b"


# ============================================================================
# Pydantic Models for Request/Response Validation
# ============================================================================


class RefineRequest(BaseModel):
    """Request body for /refine endpoint."""

    text: str = Field(..., min_length=1, description="Raw transcript text to refine")
    instructions: str | None = Field(
        None, description="Optional custom refinement instructions"
    )


class BatchTranscribeRequest(BaseModel):
    """Request body for /batch-transcribe endpoint."""

    audio_paths: list[str] = Field(
        ..., min_length=1, description="Absolute paths to audio files"
    )
    language: str = Field(default="en", description="Language code for transcription")


class SegmentResponse(BaseModel):
    """A single transcript segment."""

    start: float
    end: float
    text: str
    speaker: str | None = None
    language: str | None = None


class TranscribeResponse(BaseModel):
    """Response body for /transcribe endpoint."""

    success: bool
    segments: list[SegmentResponse]
    inference_time_s: float


class RefineResponse(BaseModel):
    """Response body for /refine endpoint."""

    success: bool
    refined_text: str
    inference_time_s: float


class BatchTranscribeResult(BaseModel):
    """Result for a single audio file in batch transcription."""

    segments: list[SegmentResponse]
    inference_time_s: float


class BatchTranscribeResponse(BaseModel):
    """Response body for /batch-transcribe endpoint."""

    success: bool
    results: list[BatchTranscribeResult]


class HealthResponse(BaseModel):
    """Response body for /health endpoint."""

    status: str
    model_loaded: bool
    model_name: str | None = None
    uptime_seconds: float | None = None
    requests_handled: int


# ============================================================================
# Helper Functions
# ============================================================================


def _segment_to_response(seg: TranscriptSegment) -> SegmentResponse:
    """Convert domain TranscriptSegment to API response model."""
    return SegmentResponse(
        start=seg.start,
        end=seg.end,
        text=seg.raw_text or "",
        speaker=None,  # Speaker diarization not yet implemented
        language=seg.language,
    )


def _load_model() -> Any:
    """Load the Canary-Qwen model into GPU memory."""
    from vociferous.engines.canary_qwen import CanaryQwenEngine
    from vociferous.engines.hardware import get_optimal_device

    device = get_optimal_device()
    logger.info(f"Loading Canary-Qwen model on {device}...")

    config = EngineConfig(
        model_name=_model_name,
        device=device,
        compute_type="fp16" if device.startswith("cuda") else "float32",
    )

    engine = CanaryQwenEngine(config)
    logger.info("Model loaded successfully")
    return engine


# ============================================================================
# FastAPI Lifespan Handler
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for model loading/unloading."""
    global _model, _model_loaded_at

    logger.info("Starting Vociferous warm model server...")
    start_time = time.time()

    try:
        _model = _load_model()
        _model_loaded_at = time.time()
        load_time = _model_loaded_at - start_time
        logger.info(f"Model ready in {load_time:.1f}s")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise

    yield  # Server runs here

    # Cleanup on shutdown
    logger.info("Shutting down server, releasing model...")
    _model = None
    _model_loaded_at = None


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Vociferous Warm Model Server",
    description="HTTP API for fast ASR inference with warm Canary-Qwen model",
    version="0.5.0",
    lifespan=lifespan,
)

# CORS middleware - localhost only for security
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:*", "http://localhost:*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ============================================================================
# Endpoints
# ============================================================================


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint.

    Returns server status, model state, uptime, and request count.
    """
    uptime = None
    if _model_loaded_at:
        uptime = time.time() - _model_loaded_at

    return HealthResponse(
        status="ready" if _model else "loading",
        model_loaded=_model is not None,
        model_name=_model_name if _model else None,
        uptime_seconds=uptime,
        requests_handled=_requests_handled,
    )


@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(audio: Annotated[UploadFile, File(...)] ) -> TranscribeResponse:
    """Transcribe uploaded audio file.

    Accepts audio file via multipart/form-data, saves to temp location,
    transcribes using warm model, and returns segments.
    """
    global _requests_handled

    if not _model:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not loaded yet, try again in a few seconds",
        )

    if not audio.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided",
        )

    # Save uploaded file to temp location
    suffix = Path(audio.filename).suffix or ".wav"
    temp_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            content = await audio.read()
            f.write(content)
            temp_path = Path(f.name)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read audio file: {e}",
        ) from e

    # Transcribe
    try:
        start_time = time.time()
        segments = _model.transcribe_file(temp_path)
        inference_time = time.time() - start_time

        _requests_handled += 1
        logger.info(
            f"Transcribed {audio.filename} in {inference_time:.2f}s "
            f"({len(segments)} segments)"
        )

        return TranscribeResponse(
            success=True,
            segments=[_segment_to_response(seg) for seg in segments],
            inference_time_s=inference_time,
        )

    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transcription failed: {e}",
        ) from e

    finally:
        # Cleanup temp file
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


@app.post("/refine", response_model=RefineResponse)
async def refine(request: RefineRequest) -> RefineResponse:
    """Refine transcript text using LLM mode.

    Takes raw transcript text and optional instructions,
    returns refined text with improved grammar and punctuation.
    """
    global _requests_handled

    if not _model:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not loaded yet",
        )

    try:
        start_time = time.time()
        refined = _model.refine_text(request.text, request.instructions)
        inference_time = time.time() - start_time

        _requests_handled += 1
        logger.info(f"Refined text in {inference_time:.2f}s")

        return RefineResponse(
            success=True,
            refined_text=refined,
            inference_time_s=inference_time,
        )

    except Exception as e:
        logger.error(f"Refinement failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Refinement failed: {e}",
        ) from e


@app.post("/batch-transcribe", response_model=BatchTranscribeResponse)
async def batch_transcribe(request: BatchTranscribeRequest) -> BatchTranscribeResponse:
    """Transcribe multiple audio files in batch.

    Takes paths to local audio files (must exist on server filesystem),
    transcribes all files using batched inference for efficiency.
    """
    global _requests_handled

    if not _model:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not loaded yet",
        )

    # Validate all paths exist
    audio_paths = [Path(p) for p in request.audio_paths]
    for p in audio_paths:
        if not p.exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Audio file not found: {p}",
            )

    try:
        start_time = time.time()

        # Use batch transcription if available
        if hasattr(_model, "transcribe_files_batch"):
            all_segments_lists = _model.transcribe_files_batch(audio_paths)
        else:
            # Fallback to sequential transcription
            all_segments_lists = [_model.transcribe_file(p) for p in audio_paths]

        total_inference_time = time.time() - start_time
        per_file_time = total_inference_time / len(audio_paths) if audio_paths else 0

        _requests_handled += len(audio_paths)
        logger.info(
            f"Batch transcribed {len(audio_paths)} files in {total_inference_time:.2f}s"
        )

        results = [
            BatchTranscribeResult(
                segments=[_segment_to_response(seg) for seg in segments],
                inference_time_s=per_file_time,
            )
            for segments in all_segments_lists
        ]

        return BatchTranscribeResponse(success=True, results=results)

    except Exception as e:
        logger.error(f"Batch transcription failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch transcription failed: {e}",
        ) from e


# ============================================================================
# Development Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")
