from __future__ import annotations

import logging
import re
import wave
from pathlib import Path
from typing import Any, Mapping
import os

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
from vociferous.domain.exceptions import DependencyError, ConfigurationError
from vociferous.engines.model_registry import normalize_model_name
from vociferous.engines.hardware import get_optimal_device, get_optimal_compute_type
from vociferous.engines.presets import (
    WHISPER_TURBO_PRESETS,
    WhisperPreset,
    get_preset_config,
    resolve_preset_name,
)

logger = logging.getLogger(__name__)

# Audio format constants
PCM16_SCALE = 32768.0  # Normalization scale for 16-bit PCM audio


def _bool_param(params: Mapping[str, str], key: str, default: bool) -> bool:
    raw = params.get(key)
    if raw is None:
        return default
    return str(raw).strip().lower() == "true"


def _float_setting(cfg: WhisperPreset, key: str, default: float) -> float:
    raw = cfg.get(key)
    if raw is None:
        return default
    if isinstance(raw, (int, float)):
        return float(raw)
    try:
        return float(str(raw))
    except (TypeError, ValueError):
        return default


def _int_setting(cfg: WhisperPreset, key: str, default: int) -> int:
    raw = cfg.get(key)
    if raw is None:
        return default
    if isinstance(raw, bool):  # Avoid treating bools as ints
        return default
    if isinstance(raw, (int, float)):
        return int(raw)
    try:
        return int(str(raw))
    except (TypeError, ValueError):
        return default


class WhisperTurboEngine(TranscriptionEngine):
    """Batch-only faster-whisper adapter for preprocessed audio files."""

    def __init__(self, config: EngineConfig) -> None:
        self.config = config
        params = {k.lower(): v for k, v in (config.params or {}).items()}

        raw_preset = params.get("preset") or params.get("profile")
        preset_name, preset_explicit = resolve_preset_name(raw_preset, WHISPER_TURBO_PRESETS, default="balanced")
        self.preset = preset_name

        self.use_mock = _bool_param(params, "use_mock", False)
        if self.use_mock:
            raise ConfigurationError("Mock mode is disabled for whisper_turbo. Remove params.use_mock=true.")

        preset_cfg = get_preset_config(self.preset, WHISPER_TURBO_PRESETS, "balanced")
        use_preset_model = (
            (preset_explicit and self.preset in WHISPER_TURBO_PRESETS)
            or config.model_name == DEFAULT_WHISPER_MODEL
        )
        target_model = preset_cfg.get("model_name") if use_preset_model else config.model_name
        self.model_name = normalize_model_name("whisper_turbo", target_model)

        # Hardware-aware defaults
        self.device = config.device if config.device != "auto" else get_optimal_device()
        self.precision = (
            config.compute_type
            if config.compute_type != "auto"
            else self._resolve_precision(self.preset, self.device)
        )

        cache_root_value = config.model_cache_dir or DEFAULT_MODEL_CACHE_DIR
        cache_root = Path(cache_root_value).expanduser()
        cache_root.mkdir(parents=True, exist_ok=True)
        self.cache_dir = cache_root

        self._model: Any | None = None
        self._pipeline: Any | None = None

        # Engine params
        default_batching = (self.preset != "custom") and not self.use_mock
        self.enable_batching = _bool_param(params, "enable_batching", default_batching)
        batch_default = int(params.get("batch_size", "0") or 0) or (8 if self.enable_batching else 1)
        self.batch_size = max(1, batch_default)
        self.word_timestamps = _bool_param(params, "word_timestamps", False)
        self.clean_disfluencies = _bool_param(params, "clean_disfluencies", True)

        beam_default = _int_setting(preset_cfg, "beam_size", 1)
        self.default_beam_size = int(params.get("default_beam_size", beam_default))
        temp_default = _float_setting(preset_cfg, "temperature", 0.0)
        self.default_temperature = float(params.get("default_temperature", temp_default))


    def _resolve_precision(self, preset: str, device: str) -> str:
        preset_cfg = get_preset_config(preset, WHISPER_TURBO_PRESETS, "balanced")
        precision_map = preset_cfg.get("precision") or {}
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
            ct_file = getattr(ctranslate2, "__file__", None)
            if ct_file:
                ct_lib_dir = (Path(ct_file).resolve().parent.parent / "ctranslate2.libs").resolve()
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

    def _transcribe(self, audio_np: np.ndarray, options: TranscriptionOptions):
        if self._model is None:
            raise RuntimeError("Model not loaded")
        model = self._model

        beam_size = options.beam_size if options.beam_size is not None else self.default_beam_size
        temperature = options.temperature if options.temperature is not None else self.default_temperature
        kwargs = {
            "language": options.language,
            "vad_filter": False,  # Always False - preprocessing handles VAD
            "word_timestamps": self.word_timestamps,
            "best_of": 1,
        }
        if beam_size is not None:
            kwargs["beam_size"] = beam_size
        if temperature is not None:
            kwargs["temperature"] = temperature
        if options.prompt:
            kwargs["initial_prompt"] = options.prompt

        try:
            pipeline = self._pipeline
            use_pipeline = self.enable_batching and pipeline is not None

            if use_pipeline and pipeline is not None:
                # BatchedInferencePipeline accepts batch_size
                kwargs["batch_size"] = self.batch_size
                result = pipeline.transcribe(audio_np, **kwargs)
            else:
                # WhisperModel.transcribe does not accept batch_size
                result = model.transcribe(audio_np, **kwargs)
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

    def transcribe_file(
        self, 
        audio_path: Path, 
        options: TranscriptionOptions
    ) -> list[TranscriptSegment]:
        """Transcribe entire audio file in one batch operation.
        
        This is the new simplified interface that processes preprocessed audio files
        without internal VAD or sliding window overlap. Audio should already be
        decoded and condensed via the audio preprocessing pipeline.
        
        Args:
            audio_path: Path to preprocessed audio file (16kHz mono PCM WAV)
            options: Transcription options (language, beam_size, etc.)
            
        Returns:
            List of transcript segments with timestamps
        """
        self._lazy_model()

        audio_np = self._load_audio_file(audio_path)

        try:
            segments_raw, _ = self._transcribe(audio_np, options)
        except Exception as exc:
            raise RuntimeError(f"Transcription failed: {exc}") from exc

        result = []
        for seg in segments_raw:
            text = self._clean_text(seg.text) if self.clean_disfluencies else seg.text
            result.append(
                TranscriptSegment(
                    text=text.strip(),
                    start_s=seg.start,
                    end_s=seg.end,
                    language=options.language,
                    confidence=getattr(seg, "avg_logprob", 0.0),
                )
            )

        return result
    
    def _load_audio_file(self, audio_path: Path) -> np.ndarray:
        """Load audio file and convert to numpy array for transcription.
        
        Note: This method is duplicated in both WhisperTurboEngine and VoxtralLocalEngine
        to keep engines independent. Future refactoring could extract to shared utility.
        
        Args:
            audio_path: Path to audio file (should be 16kHz mono PCM WAV)
            
        Returns:
            Normalized float32 numpy array of audio samples
        """
        # Read WAV file
        with wave.open(str(audio_path), 'rb') as wf:
            if wf.getnchannels() != 1:
                raise ValueError(f"Expected mono audio, got {wf.getnchannels()} channels")
            if wf.getsampwidth() != 2:
                raise ValueError(f"Expected 16-bit audio, got {wf.getsampwidth() * 8}-bit")
            if wf.getframerate() != 16000:
                raise ValueError(f"Expected 16kHz audio, got {wf.getframerate()}Hz")
            
            # Read all frames
            frames = wf.readframes(wf.getnframes())
        
        # Convert to numpy array and normalize
        audio_np = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / PCM16_SCALE
        return audio_np

    @property
    def metadata(self) -> EngineMetadata:
        """Return engine metadata for result building."""
        return EngineMetadata(
            model_name=self.model_name,
            device=self.device,
            precision=self.precision,
        )
