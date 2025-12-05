from __future__ import annotations

import os
from pathlib import Path
from typing import List

from chatterbug.domain.model import (
    DEFAULT_MODEL_CACHE_DIR,
    EngineConfig,
    EngineMetadata,
    TranscriptSegment,
    TranscriptionEngine,
    TranscriptionOptions,
)
from chatterbug.domain.exceptions import DependencyError, EngineError
from chatterbug.engines.model_registry import normalize_model_name


class ParakeetEngine(TranscriptionEngine):
    """Experimental offline Parakeet RNNT engine backed by NeMo models cached locally."""

    def __init__(self, config: EngineConfig) -> None:
        self.config = config
        self.model_name = normalize_model_name("parakeet_rnnt", config.model_name)
        self.device = config.device
        self.precision = config.compute_type
        cache_root = Path(config.model_cache_dir or DEFAULT_MODEL_CACHE_DIR).expanduser()
        cache_root.mkdir(parents=True, exist_ok=True)
        self.cache_dir = cache_root
        
        self._buffer = bytearray()
        self._segments: List[TranscriptSegment] = []
        self._options: TranscriptionOptions | None = None
        self._model = None
        self._sample_rate = 16000
        self._punct_model = None

    def _lazy_model(self):
        if self._model is not None:
            return
        try:
            import logging
            import torch
            from nemo.collections.asr.models import EncDecRNNTBPEModel
            
            # Suppress verbose NeMo logging
            logging.getLogger("nemo_logger").setLevel(logging.ERROR)
        except ImportError as exc:  # pragma: no cover - optional dependency guard
            raise DependencyError(
                "nemo_toolkit is required for ParakeetEngine; install with parakeet extra"
            ) from exc

        # Hint Nemo to cache under our model cache
        os.environ.setdefault("NEMO_CACHE_DIR", str(self.cache_dir))

        # Load local RNNT model (no endpoints). Ensure GPU is used when available.
        map_location = "cuda" if self.device == "cuda" else "cpu"
        model = EncDecRNNTBPEModel.from_pretrained(
            model_name=self.model_name,
            map_location=map_location,
        )

        # Precision selection: fall back to fp32 on CPU; prefer fp16 on CUDA.
        if self.device == "cuda":
            model = model.to(dtype=torch.float16)
        else:
            model = model.to(dtype=torch.float32)

        self._model = model.to(self.device)
        # Parakeet RNNT models are 16 kHz mono
        self._sample_rate = 16000

    def _lazy_punct_model(self):
        if self._punct_model is not None:
            return
        try:
            from nemo.collections.nlp.models import PunctuationCapitalizationModel
        except ImportError:
            # Punctuation is optional; skip if nemo nlp extras are absent
            return

        os.environ.setdefault("NEMO_CACHE_DIR", str(self.cache_dir))
        self._punct_model = PunctuationCapitalizationModel.from_pretrained(
            model_name="punctuation_en_bert",
            cache_dir=str(self.cache_dir),
        )

    def _apply_punctuation(self, text: str) -> str:
        if not text.strip():
            return text
        self._lazy_punct_model()
        if self._punct_model is None:
            # Heuristic fallback: capitalize first char, add period if missing.
            capped = text[:1].upper() + text[1:]
            if capped and capped[-1] not in {".", "?", "!"}:
                capped = capped + "."
            return capped
        try:
            result = self._punct_model.add_punctuation_capitalization([text])
            if result and isinstance(result, list):
                return result[0]
        except Exception:
            return text
        return text

    def start(self, options: TranscriptionOptions) -> None:
        self._options = options
        self._buffer.clear()
        self._segments.clear()
        self._lazy_model()

    def push_audio(self, pcm16: bytes, timestamp_ms: int) -> None:
        self._buffer.extend(pcm16)

    def flush(self) -> None:
        if not self._buffer:
            return

        if self._model is None:
            raise EngineError("Parakeet model not loaded")

        # Convert buffered PCM16 directly to torch tensor for inference
        try:
            import numpy as np
            import torch
        except ImportError as exc:  # pragma: no cover
            raise DependencyError("numpy and torch required for tensor conversion") from exc

        audio_bytes = bytes(self._buffer)
        num_samples = len(audio_bytes) // 2
        duration_s = num_samples / float(self._sample_rate)

        # Convert PCM16 bytes directly to float32 tensor
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        audio_tensor = torch.tensor(audio_np).unsqueeze(0).to(self.device)
        audio_lengths = torch.tensor([len(audio_np)], dtype=torch.long).to(self.device)

        try:
            # NeMo's transcribe() method signature may vary by version
            # Common patterns: audio/audio_len or paths_2_audio_files
            # Try tensor-based inference first (faster, no temp files)
            texts = self._model.transcribe(
                audio=audio_tensor,
                audio_len=audio_lengths,
                batch_size=1,
            )
            text = ""
            if texts:
                first = texts[0]
                # NeMo may return str, list[str], or Hypothesis objects depending on version
                if isinstance(first, str):
                    text = first
                elif isinstance(first, list) and first:
                    inner = first[0]
                    if hasattr(inner, "text"):
                        text = inner.text
                    else:
                        text = str(inner)
                elif hasattr(first, "text"):
                    text = first.text
        except Exception as exc:
            raise EngineError(f"Parakeet inference failed: {exc}") from exc

        if text.strip():
            final_text = self._apply_punctuation(text.strip())
            self._segments.append(
                TranscriptSegment(
                    text=final_text,
                    start_s=0.0,
                    end_s=duration_s,
                    language=self._options.language if self._options else "auto",
                    confidence=1.0,
                )
            )

        self._buffer.clear()

    def poll_segments(self) -> List[TranscriptSegment]:
        segs = list(self._segments)
        self._segments.clear()
        return segs

    @property
    def metadata(self) -> EngineMetadata:
        """Return engine metadata for result building."""
        return EngineMetadata(
            model_name=self.model_name,
            device=self.device,
            precision=self.precision,
        )
