"""
Official OpenAI Whisper engine for local ASR.

Uses the official openai-whisper package (NOT faster-whisper, NOT CTranslate2).
Supports Whisper Turbo, V3, and Large models.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from vociferous.domain.exceptions import DependencyError
from vociferous.domain.model import (
    DEFAULT_MODEL_CACHE_DIR,
    EngineConfig,
    EngineMetadata,
    TranscriptionEngine,
    TranscriptionOptions,
    TranscriptSegment,
)
from vociferous.engines.hardware import get_optimal_device
from vociferous.engines.model_registry import normalize_model_name

logger = logging.getLogger(__name__)


class WhisperTurboEngine(TranscriptionEngine):
    """Official OpenAI Whisper engine for CPU/GPU batch transcription.
    
    Uses the official openai-whisper package. Supports Turbo, V3, and Large models.
    Does NOT use faster-whisper or CTranslate2.
    
    Note: Whisper is ASR-only and does not support text refinement.
    For refinement, use Canary-Qwen engine instead.
    """

    def __init__(self, config: EngineConfig) -> None:
        self.config = config
        self.model_name = normalize_model_name("whisper_turbo", config.model_name)
        
        # Device defaults (OpenAI Whisper uses "cuda" or "cpu")
        self.device = config.device if config.device != "auto" else get_optimal_device()
        self.precision = config.compute_type if config.compute_type != "auto" else "float16"
        
        cache_root = Path(config.model_cache_dir or DEFAULT_MODEL_CACHE_DIR).expanduser()
        cache_root.mkdir(parents=True, exist_ok=True)
        self.cache_dir = cache_root
        
        self._model: Any = None
        self._lazy_model()

    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            model_name=self.model_name,
            device=self.device,
            precision=self.precision,
        )

    def transcribe_file(
        self,
        audio_path: Path,
        options: TranscriptionOptions | None = None,
    ) -> list[TranscriptSegment]:
        """Transcribe entire audio file in batch using official Whisper.
        
        Args:
            audio_path: Path to preprocessed audio file (16kHz mono WAV recommended)
            options: Transcription options (language, etc.)
            
        Returns:
            List of TranscriptSegment with raw_text populated
            
        Raises:
            DependencyError: If Whisper model is not loaded
        """
        if self._model is None:
            raise DependencyError(
                "Whisper model not loaded",
                suggestions=["Install openai-whisper: pip install openai-whisper"],
            )
        
        resolved_options = options or TranscriptionOptions()
        
        # Use inference mode for faster inference if torch is available
        try:
            import torch
            inference_context = torch.inference_mode()
        except ImportError:
            from contextlib import nullcontext
            inference_context = nullcontext()
        
        with inference_context:
            # Official Whisper transcribe() accepts file path directly
            result = self._model.transcribe(
                str(audio_path),
                language=resolved_options.language if resolved_options.language != "auto" else None,
                fp16=(self.device == "cuda" and self.precision in ("float16", "fp16")),
            )
        
        # Convert to domain segments
        result_segments: list[TranscriptSegment] = []
        for idx, seg in enumerate(result.get("segments", [])):
            text = seg.get("text", "").strip()
            if not text:
                continue  # Skip empty segments
            result_segments.append(
                TranscriptSegment(
                    id=f"segment-{idx}",
                    start=float(seg["start"]),
                    end=float(seg["end"]),
                    raw_text=text,
                    language=resolved_options.language if resolved_options.language != "auto" else None,
                )
            )
        
        return result_segments

    def _lazy_model(self) -> None:
        """Lazy-load official Whisper model on first use."""
        if self._model is not None:
            return
        
        try:
            import whisper
        except ImportError as exc:
            raise DependencyError(
                "openai-whisper package required",
                suggestions=[
                    "Install with: pip install openai-whisper",
                    "Or: pip install -e .[whisper]",
                ],
            ) from exc
        
        logger.info(
            "Loading Whisper model: %s (device=%s, precision=%s)",
            self.model_name,
            self.device,
            self.precision,
        )
        
        # Official Whisper uses model size names
        self._model = whisper.load_model(
            self.model_name,
            device=self.device,
            download_root=str(self.cache_dir),
        )
        
        logger.info("Whisper model loaded successfully")
