"""
vLLM-backed Whisper engine for high-accuracy transcription.

This engine communicates with a local vLLM server running Whisper models via the
OpenAI-compatible audio API. This is the recommended approach for production
Whisper deployments prioritizing accuracy and GPU efficiency.

Usage:
    1. Start the vLLM server:
       ```bash
       vllm serve openai/whisper-large-v3-turbo --dtype bfloat16
       ```

    2. Use this engine:
       ```bash
       chatterbug transcribe audio.flac --engine whisper_vllm
       ```

The vLLM server handles all GPU acceleration, audio preprocessing, and
model inference efficiently using paged attention and optimized kernels.

Presets:
    - high_accuracy: whisper-large-v3, beam=2, deterministic (slowest, best WER)
    - balanced: whisper-large-v3-turbo, beam=1 (default, good speed/accuracy)
    - fast: whisper-large-v3-turbo, beam=1, aggressive chunking (fastest)
"""
from __future__ import annotations

import base64
import io
import logging
from typing import TYPE_CHECKING, List
import wave
from pathlib import Path

if TYPE_CHECKING:
    import openai

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

logger = logging.getLogger(__name__)

# Default vLLM server endpoint
DEFAULT_VLLM_ENDPOINT = "http://localhost:8000"

# Preset configurations mapping preset names to model + decoding params
WHISPER_VLLM_PRESETS = {
    "high_accuracy": {
        "model": "openai/whisper-large-v3",
        "beam_size": 2,
        "temperature": 0.0,
    },
    "balanced": {
        "model": "openai/whisper-large-v3-turbo",
        "beam_size": 1,
        "temperature": 0.0,
    },
    "fast": {
        "model": "openai/whisper-large-v3-turbo",
        "beam_size": 1,
        "temperature": 0.0,
    },
}


class WhisperVLLMEngine(TranscriptionEngine):
    """
    vLLM-backed Whisper engine using OpenAI-compatible audio API.

    This engine delegates all heavy computation to a vLLM server,
    which provides optimal GPU utilization with paged attention,
    tensor parallelism, and efficient audio processing.

    Supports accuracy-first presets while maintaining the push-based
    streaming interface expected by TranscriptionSession.
    """

    def __init__(self, config: EngineConfig) -> None:
        self.config = config
        self.model_name = normalize_model_name("whisper_vllm", config.model_name)

        # Extract vLLM endpoint from params or use default
        params = config.params or {}
        self.endpoint = params.get("vllm_endpoint", DEFAULT_VLLM_ENDPOINT)

        # vLLM handles device/precision internally - we just report what we requested
        self.device = config.device if config.device != "auto" else "cuda"
        self.precision = config.compute_type if config.compute_type != "auto" else "bfloat16"

        self._client: "openai.OpenAI | None" = None
        self._buffer = bytearray()
        self._segments: List[TranscriptSegment] = []
        self._options: TranscriptionOptions | None = None
        self._sample_rate = 16000

    def _lazy_client(self) -> None:
        """Lazily initialize the OpenAI client."""
        if self._client is not None:
            return

        try:
            import openai
        except ImportError as exc:
            raise DependencyError(
                "openai package is required for vLLM integration; pip install openai"
            ) from exc

        # OpenAI client configured to talk to local vLLM server
        self._client = openai.OpenAI(
            base_url=f"{self.endpoint}/v1",
            api_key="EMPTY",  # vLLM doesn't require auth by default
        )

        # Discover what model(s) are actually loaded in vLLM
        self._discover_served_model()

        logger.info(f"Connected to vLLM server at {self.endpoint}, using model: {self.model_name}")

    def _discover_served_model(self) -> None:
        """Query vLLM to discover what model is actually being served.

        vLLM can only serve one model at a time (unless using multi-model setup).
        This ensures we use the correct model name in API requests and warns
        if there's a mismatch with what the user requested.
        """
        if self._client is None:
            return

        try:
            models = self._client.models.list()
            served_models = [m.id for m in models.data]

            if not served_models:
                logger.warning("vLLM server reports no models loaded")
                return

            # Use the first (usually only) model served by vLLM
            served_model = served_models[0]

            # Check if requested model matches what's served
            # Handle both full names and vLLM's abbreviated versions
            if self.model_name != served_model and not served_model.endswith(self.model_name.split("/")[-1]):
                logger.warning(
                    f"Requested model '{self.model_name}' differs from vLLM served model '{served_model}'. "
                    f"Using served model."
                )
                self.model_name = served_model

        except Exception as exc:
            # If we can't query models, try to proceed anyway - vLLM might be starting up
            # or the endpoint might not support the models API
            logger.debug(f"Could not query vLLM models endpoint: {exc}")

    def start(self, options: TranscriptionOptions) -> None:
        """Initialize the engine with session-specific options."""
        self._options = options
        self._buffer.clear()
        self._segments.clear()
        self._lazy_client()

        # Apply preset if specified and no explicit model override
        if hasattr(options, 'preset') and options.preset:
            preset_config = WHISPER_VLLM_PRESETS.get(options.preset)
            if preset_config and not options.params.get("model_override"):
                # Preset can suggest a model, but explicit config.model_name takes precedence
                preset_model = preset_config.get("model")
                if preset_model and self.config.model_name == normalize_model_name("whisper_vllm", None):
                    # Only use preset model if user didn't specify one
                    self.model_name = normalize_model_name("whisper_vllm", preset_model)
                    logger.debug(f"Applied preset '{options.preset}' model: {self.model_name}")

    def push_audio(self, pcm16: bytes, timestamp_ms: int) -> None:
        """Append raw 16 kHz mono PCM16 audio to the internal buffer."""
        self._buffer.extend(pcm16)

    def _encode_audio_wav(self, pcm16_bytes: bytes) -> bytes:
        """Convert PCM16 audio to WAV format for the API."""
        import numpy as np

        # Convert bytes to numpy array
        audio_np = np.frombuffer(pcm16_bytes, dtype=np.int16)

        # Write to WAV format in memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self._sample_rate)
            wav_file.writeframes(audio_np.tobytes())

        wav_buffer.seek(0)
        return wav_buffer.read()

    def flush(self) -> None:
        """Force processing of whatever is currently buffered."""
        if not self._buffer:
            return

        import numpy as np

        audio_bytes = bytes(self._buffer)
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
        duration_s = len(audio_np) / self._sample_rate

        # Encode audio as WAV
        wav_bytes = self._encode_audio_wav(audio_bytes)

        # Build the transcription request using Whisper audio API
        language = self._options.language if self._options else None

        # Get parameters (preset or explicit)
        params = self._options.params if self._options else {}
        response_format = params.get("response_format", "verbose_json")

        # Apply preset parameters if set
        preset_name = getattr(self._options, 'preset', None) if self._options else None
        if preset_name and preset_name in WHISPER_VLLM_PRESETS:
            preset_config = WHISPER_VLLM_PRESETS[preset_name]
            # Preset params are overridden by explicit params
            temperature = float(params.get("temperature", preset_config.get("temperature", 0.0)))
        else:
            temperature = float(params.get("temperature", "0.0") or "0.0")

        if self._client is None:
            raise EngineError("vLLM client not initialized - call start() first")

        try:
            # Use OpenAI audio transcriptions API
            # The client expects a file-like object or tuple (filename, file_bytes, mime_type)
            response = self._client.audio.transcriptions.create(
                model=self.model_name,
                file=("audio.wav", wav_bytes, "audio/wav"),
                language=language,
                response_format=response_format,
                temperature=temperature if temperature > 0 else 0.0,
            )

            # Parse response based on format
            if response_format == "verbose_json":
                # Extract segments with timestamps
                if hasattr(response, 'segments') and response.segments:
                    for seg in response.segments:
                        self._segments.append(TranscriptSegment(
                            text=seg.get('text', '').strip(),
                            start_s=seg.get('start', 0.0),
                            end_s=seg.get('end', duration_s),
                            language=language or response.language or "en",
                            confidence=1.0,  # vLLM doesn't provide per-segment confidence
                        ))
                elif hasattr(response, 'text') and response.text:
                    # Fallback if no segments but text is present
                    self._segments.append(TranscriptSegment(
                        text=response.text.strip(),
                        start_s=0.0,
                        end_s=duration_s,
                        language=language or getattr(response, 'language', 'en'),
                        confidence=1.0,
                    ))
            else:
                # Plain text response
                transcription = response if isinstance(response, str) else getattr(response, 'text', '')
                if transcription.strip():
                    self._segments.append(TranscriptSegment(
                        text=transcription.strip(),
                        start_s=0.0,
                        end_s=duration_s,
                        language=language or "en",
                        confidence=1.0,
                    ))

        except Exception as exc:
            logger.error(f"vLLM transcription failed: {exc}")
            raise EngineError(
                f"vLLM transcription failed: {exc}. "
                f"Ensure vLLM server is running at {self.endpoint} with a Whisper model loaded. "
                f"Run 'chatterbug check-vllm' to diagnose or use --engine whisper_turbo for local fallback."
            ) from exc

        self._buffer.clear()

    def poll_segments(self) -> list[TranscriptSegment]:
        """Return any new segments produced since last call."""
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
