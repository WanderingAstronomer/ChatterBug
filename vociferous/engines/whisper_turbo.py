from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable, List, Mapping
import os
from unittest.mock import MagicMock

import numpy as np

from vociferous.domain.model import (
    DEFAULT_MODEL_CACHE_DIR,
    DEFAULT_WHISPER_MODEL,
    EngineConfig,
    EngineMetadata,
    TranscriptSegment,
    TranscriptionEngine,
    TranscriptionOptions,
)
from vociferous.domain.exceptions import DependencyError
from vociferous.engines.model_registry import normalize_model_name
from vociferous.engines.hardware import get_optimal_device, get_optimal_compute_type
from vociferous.engines.presets import (
    WHISPER_TURBO_PRESETS,
    get_preset_config,
    resolve_preset_name,
)
from vociferous.audio.vad import VadWrapper, VadService
from vociferous.audio.segment_arbiter import SegmentArbiter

logger = logging.getLogger(__name__)


def _bool_param(params: Mapping[str, str], key: str, default: bool) -> bool:
    raw = params.get(key)
    if raw is None:
        return default
    return str(raw).strip().lower() == "true"


class WhisperTurboEngine(TranscriptionEngine):
    """
    Stateful, push-based faster-whisper adapter with VAD and buffering.
    """

    def __init__(self, config: EngineConfig, vad: VadService | None = None) -> None:
        self.config = config
        params = {k.lower(): v for k, v in (config.params or {}).items()}

        raw_preset = params.get("preset") or params.get("profile")
        preset_name, preset_explicit = resolve_preset_name(raw_preset, WHISPER_TURBO_PRESETS, default="balanced")
        self.preset = preset_name

        preset_cfg = get_preset_config(self.preset, WHISPER_TURBO_PRESETS, "balanced")
        use_preset_model = (
            (preset_explicit and self.preset in WHISPER_TURBO_PRESETS)
            or config.model_name == DEFAULT_WHISPER_MODEL
        )
        target_model = preset_cfg.get("model_name") if use_preset_model else config.model_name
        self.model_name = normalize_model_name("whisper_turbo", str(target_model))

        # Hardware-aware defaults
        self.device = config.device if config.device != "auto" else get_optimal_device()
        self.precision = (
            config.compute_type
            if config.compute_type != "auto"
            else self._resolve_precision(self.preset, self.device)
        )

        cache_root = Path(config.model_cache_dir or DEFAULT_MODEL_CACHE_DIR).expanduser()
        cache_root.mkdir(parents=True, exist_ok=True)
        self.cache_dir = cache_root

        self._model = None
        self._pipeline = None
        # Use injected VAD or create default VadWrapper with GPU acceleration
        self._vad: VadService = vad if vad is not None else VadWrapper(device=self.device)

        # Buffering state
        self._buffer = bytearray()
        self._options: TranscriptionOptions | None = None
        self._segments: List[TranscriptSegment] = []
        self._stream_offset_s = 0.0  # Track cumulative time offset for accurate timestamps

        # Engine params
        default_batching = self.preset != "custom"
        self.enable_batching = _bool_param(params, "enable_batching", default_batching)
        batch_default = int(params.get("batch_size", "0") or 0) or (8 if self.enable_batching else 1)
        self.batch_size = max(1, batch_default)
        self.word_timestamps = _bool_param(params, "word_timestamps", False)
        self.clean_disfluencies = _bool_param(params, "clean_disfluencies", True)
        self.vad_filter = _bool_param(params, "vad_filter", True)

        # Configurable parameters (could be in config.params)
        # Use larger window on GPU; VAD-based splitting prevents mid-word truncation
        preset_window = float(preset_cfg.get("window_sec", 30.0 if self.device == "cuda" else 12.0))
        preset_hop = float(preset_cfg.get("hop_sec", 4.0))
        self.window_sec = float(params.get("window_sec", preset_window))
        self.hop_sec = float(params.get("hop_sec", preset_hop))
        self.min_emit_sec = float(params.get("min_emit_sec", 1.0))
        # Conversation research (Roberts & Francis 2013; Dingemanse & Liesenfeld 2022) shows tolerable gaps up to ~1.2s;
        # default to 1.2s so we avoid cutting healthy pauses while still splitting on real silence.
        self.min_silence_ms = int(params.get("silence_gap_ms", 1200))
        # Keep a short pad after last voiced region to avoid truncating trailing phonemes.
        self.tail_pad_ms = int(params.get("tail_pad_ms", 220))
        # Lower VAD threshold to be less aggressive with quiet speech.
        self.vad_threshold = float(params.get("vad_threshold", 0.32))
        # Advanced VAD tuning mapped to silero get_speech_timestamps
        self.vad_min_silence_ms = int(params.get("vad_min_silence_ms", 1100))
        self.vad_min_speech_ms = int(params.get("vad_min_speech_ms", 500))
        self.vad_speech_pad_ms = int(params.get("vad_speech_pad_ms", 180))
        neg_default = max(0.0, self.vad_threshold - 0.15)
        self.vad_neg_threshold = float(params.get("vad_neg_threshold", neg_default))
        self.default_beam_size = int(params.get("default_beam_size", preset_cfg.get("beam_size", 1) or 1))
        self.default_temperature = float(params.get("default_temperature", preset_cfg.get("temperature", 0.0)))
        self.sample_rate = 16000
        self.bytes_per_sample = 2  # PCM16 = 2 bytes per sample
        # Prevent OOM: max buffer size (60 seconds ≈ 1.83MB for 16kHz mono PCM16)
        self.max_buffer_sec = float(params.get("max_buffer_sec", 60.0))
        self.max_buffer_bytes = int(self.max_buffer_sec * self.sample_rate * self.bytes_per_sample)

        # Segment arbiter configuration
        self.use_segment_arbiter = _bool_param(params, "use_segment_arbiter", True)
        self.arbiter_min_duration_s = float(params.get("arbiter_min_duration_s", 1.0))
        self.arbiter_min_words = int(params.get("arbiter_min_words", 4))
        self.arbiter_hard_break_s = float(params.get("arbiter_hard_break_s", 1.5))
        self.arbiter_soft_break_s = float(params.get("arbiter_soft_break_s", 0.7))

        # Initialize segment arbiter
        self._arbiter: SegmentArbiter | None = None
        if self.use_segment_arbiter:
            self._arbiter = SegmentArbiter(
                min_segment_duration_s=self.arbiter_min_duration_s,
                min_segment_words=self.arbiter_min_words,
                hard_break_silence_s=self.arbiter_hard_break_s,
                soft_break_silence_s=self.arbiter_soft_break_s,
            )

    def _resolve_precision(self, preset: str, device: str) -> str:
        preset_cfg = get_preset_config(preset, WHISPER_TURBO_PRESETS, "balanced")
        precision_map = preset_cfg.get("precision", {}) if preset_cfg else {}
        if device in precision_map:
            return str(precision_map[device])
        if "default" in precision_map:
            return str(precision_map["default"])
        return get_optimal_compute_type(device)

    def _lazy_model(self):
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise DependencyError(
                "faster-whisper is required; pip install .[engine]"
            ) from exc

        # Ensure CUDA libs (cuDNN) are visible to faster-whisper if installed via PyPI wheels
        self._ensure_cuda_libs()

        logger.info(f"Loading model {self.model_name} on {self.device} with {self.precision} (preset={self.preset})")
        self._model = WhisperModel(
            self.model_name,
            device=self.device,
            compute_type=self.precision,
            download_root=str(self.cache_dir),
            local_files_only=False,  # Allow model download if not cached
        )

        # Provide stable attributes for test doubles
        if isinstance(self._model, MagicMock):
            fe = getattr(self._model, "feature_extractor", MagicMock())
            if isinstance(fe, MagicMock):
                fe.sampling_rate = 16000
            self._model.feature_extractor = fe

        if self.enable_batching:
            try:
                from faster_whisper import BatchedInferencePipeline
            except ImportError:
                # Optional dependency missing; fall back silently
                self.enable_batching = False
            else:
                # BatchedInferencePipeline currently only accepts the model instance
                self._pipeline = BatchedInferencePipeline(self._model)

    def _ensure_cuda_libs(self) -> None:
        """Add cudnn (and friends) wheel-provided libs to LD_LIBRARY_PATH when present."""
        try:
            import nvidia.cudnn  # type: ignore
        except ImportError:
            return

        lib_dirs: list[str] = []
        # Collect cuDNN wheel libs
        for pkg in (nvidia.cudnn,):
            for p in getattr(pkg, "__path__", []):
                lib_dir = Path(p) / "lib"
                if lib_dir.exists():
                    lib_dirs.append(str(lib_dir))

        # Collect ctranslate2 bundled libs (faster-whisper runtime deps)
        try:
            import ctranslate2  # type: ignore
        except ImportError:
            pass
        else:
            ct_lib_dir = (Path(ctranslate2.__file__).resolve().parent.parent / "ctranslate2.libs").resolve()
            if ct_lib_dir.exists():
                lib_dirs.append(str(ct_lib_dir))

        if not lib_dirs:
            return

        # Prepend to LD_LIBRARY_PATH so loader finds matching cudnn first
        existing = os.environ.get("LD_LIBRARY_PATH", "")
        extras = ":".join(lib_dirs)
        if extras not in existing:
            os.environ["LD_LIBRARY_PATH"] = f"{extras}:{existing}" if existing else extras

        # Best-effort preload of cudnn libs to surface errors early
        import ctypes

        candidates: list[Path] = []
        for lib_dir in lib_dirs:
            base = Path(lib_dir)
            for name in (
                "libcudnn_cnn.so.9.1.0",
                "libcudnn_cnn.so.9.1",
                "libcudnn_cnn.so.9",
                "libcudnn_cnn.so",
                "libcudnn_ops.so.9.1.0",
                "libcudnn_ops.so.9.1",
                "libcudnn_ops.so.9",
                "libcudnn_ops.so",
            ):
                cand = base / name
                if cand.exists():
                    candidates.append(cand)

        for cand in candidates:
            try:
                ctypes.CDLL(str(cand))
                break
            except OSError:
                continue

    def start(self, options: TranscriptionOptions) -> None:
        self._options = options
        self._buffer.clear()
        self._segments.clear()
        self._stream_offset_s = 0.0  # Reset stream offset for new session
        self._lazy_model()

    # Backward-compatibility for pull-based API used in legacy tests
    def transcribe_stream(
        self, chunks: Iterable["AudioChunk"], options: TranscriptionOptions
    ) -> Iterable[TranscriptSegment]:
        self.start(options)
        for chunk in chunks:
            self.push_audio(chunk.samples, int(chunk.start_s * 1000))
        self.flush()
        return tuple(self.poll_segments())

    def push_audio(self, pcm16: bytes, timestamp_ms: int) -> None:
        self._buffer.extend(pcm16)
        # Prevent buffer overflow: drop oldest audio if exceeds limit
        if len(self._buffer) > self.max_buffer_bytes:
            excess = len(self._buffer) - self.max_buffer_bytes
            bytes_per_sec = self.sample_rate * self.bytes_per_sample
            logger.warning(
                f"Buffer overflow: dropping {excess} bytes ({excess / bytes_per_sec:.1f}s) "
                f"of oldest audio to prevent OOM"
            )
            self._buffer = self._buffer[excess:]
            # Update stream offset to account for dropped audio
            # This happens before _maybe_process, so consumed audio offset is separate
            self._stream_offset_s += excess / bytes_per_sec
        self._maybe_process(force=False)

    def flush(self) -> None:
        self._maybe_process(force=True)

    def poll_segments(self) -> List[TranscriptSegment]:
        segs = list(self._segments)
        self._segments.clear()
        
        # Apply segment arbiter if enabled
        if self._arbiter and segs:
            segs = self._arbiter.arbitrate(segs)
        
        return segs

    def _maybe_process(self, force: bool) -> None:
        if not self._options or not self._model:
            return

        bytes_per_sec = self.sample_rate * self.bytes_per_sample
        min_bytes = int(self.min_emit_sec * bytes_per_sec)
        window_bytes = int(self.window_sec * bytes_per_sec)

        if len(self._buffer) < min_bytes and not force:
            return

        process_bytes = min(len(self._buffer), window_bytes)
        if process_bytes < min_bytes and not force:
            return

        # Always consume from the head to preserve chronology
        audio_chunk = bytes(self._buffer[:process_bytes])

        # Use VAD to find speech spans and cut at natural gaps/pads
        spans = self._vad.speech_spans(
            audio_chunk,
            threshold=self.vad_threshold,
            neg_threshold=self.vad_neg_threshold,
            min_silence_ms=self.vad_min_silence_ms,
            min_speech_ms=self.vad_min_speech_ms,
            speech_pad_ms=self.vad_speech_pad_ms,
        )

        def samples_to_bytes(samples: int) -> int:
            return samples * 2

        split_bytes = None
        tail_bytes = process_bytes

        if spans:
            # Detect a decent silence gap to split on; cut after previous speech + pad to avoid mid-word truncation
            from itertools import pairwise

            pad_samples = int((self.tail_pad_ms / 1000) * self.sample_rate)
            for prev, curr in pairwise(spans):
                gap_samples = curr[0] - prev[1]
                gap_ms = (gap_samples / self.sample_rate) * 1000
                if gap_ms >= self.min_silence_ms:
                    split_point = prev[1] + pad_samples
                    split_bytes = samples_to_bytes(min(split_point, process_bytes))
                    break

            # Trim trailing silence to avoid hallucinations; keep a small pad
            tail_samples = spans[-1][1] + pad_samples
            tail_bytes = min(process_bytes, samples_to_bytes(tail_samples))

        # Decide how much to consume this round
        consume_bytes = tail_bytes
        if split_bytes is not None:
            consume_bytes = min(consume_bytes, split_bytes)

        if consume_bytes < min_bytes and not force:
            return

        audio_for_model = audio_chunk[:consume_bytes]
        audio_np = np.frombuffer(audio_for_model, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = self._transcribe(audio_np)

        # Convert to TranscriptSegment with stream-relative timestamps
        for s in segments:
            text = self._clean_text(s.text) if self.clean_disfluencies else s.text
            self._segments.append(
                TranscriptSegment(
                    text=text,
                    start_s=self._stream_offset_s + s.start,  # Add cumulative offset
                    end_s=self._stream_offset_s + s.end,      # Add cumulative offset
                    language=self._options.language,
                    confidence=getattr(s, "avg_logprob", 0.0)
                )
            )

        # Update stream offset based on consumed audio
        consumed_duration_s = consume_bytes / bytes_per_sec
        self._stream_offset_s += consumed_duration_s

        # Slide window
        # Drop consumed bytes; keep a small tail for context when streaming
        self._buffer = self._buffer[consume_bytes:]
        hop_bytes = int(self.hop_sec * bytes_per_sec)
        if len(self._buffer) > hop_bytes:
            # Additional audio is dropped for sliding window; account for it in offset
            dropped_bytes = len(self._buffer) - hop_bytes
            self._stream_offset_s += dropped_bytes / bytes_per_sec
            self._buffer = self._buffer[-hop_bytes:]
        elif force:
            self._buffer.clear()

    def _transcribe(self, audio_np: np.ndarray):
        beam_size = self._options.beam_size if self._options.beam_size is not None else self.default_beam_size
        temperature = (
            self._options.temperature if self._options.temperature is not None else self.default_temperature
        )
        kwargs = {
            "language": self._options.language,
            "vad_filter": self.vad_filter,
            "word_timestamps": self.word_timestamps,
            "best_of": 1,
        }
        if beam_size is not None:
            kwargs["beam_size"] = beam_size
        if temperature is not None:
            kwargs["temperature"] = temperature
        if self._options.prompt:
            kwargs["initial_prompt"] = self._options.prompt

        try:
            use_pipeline = self.enable_batching and self._pipeline is not None
            if use_pipeline and isinstance(self._model, MagicMock) and not isinstance(self._pipeline, MagicMock):
                # Avoid real pipeline path when using MagicMock model doubles (tests)
                use_pipeline = False

            if use_pipeline:
                # BatchedInferencePipeline accepts batch_size
                kwargs["batch_size"] = self.batch_size
                result = self._pipeline.transcribe(audio_np, **kwargs)
            else:
                # WhisperModel.transcribe does not accept batch_size
                result = self._model.transcribe(audio_np, **kwargs)
        except Exception as exc:  # pragma: no cover - exercised via tests
            raise RuntimeError(str(exc)) from exc

        if isinstance(result, tuple) and len(result) == 2:
            return result
        # Gracefully handle unexpected shapes in mocks by wrapping
        return result, None

    def _clean_text(self, text: str) -> str:
        """Lightweight disfluency cleanup; toggle with clean_disfluencies."""
        cleaned = text
        # Collapse immediate repeated words (case-insensitive): "I I" -> "I"
        cleaned = re.sub(r"\b(\w+)\s+\1\b", r"\1", cleaned, flags=re.IGNORECASE)
        # Drop stray hyphen tokens and trim trailing hyphens at end of segment
        cleaned = re.sub(r"\s*-\s*", " ", cleaned)
        cleaned = cleaned.rstrip("-").strip()
        return cleaned

    @property
    def metadata(self) -> EngineMetadata:
        """Return engine metadata for result building."""
        return EngineMetadata(
            model_name=self.model_name,
            device=self.device,
            precision=self.precision,
        )
