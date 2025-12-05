"""
vLLM-backed Voxtral engine for high-performance transcription.

This engine communicates with a local vLLM server running Voxtral via the
OpenAI-compatible API. This is the officially recommended approach for
production Voxtral deployments per Mistral's documentation.

Usage:
    1. Start the vLLM server:
       ```bash
       vllm serve mistralai/Voxtral-Mini-3B-2507 \
         --tokenizer_mode mistral \
         --config_format mistral \
         --load_format mistral \
         --dtype bfloat16
       ```

    2. Use this engine:
       ```bash
       chatterbug transcribe audio.flac --engine voxtral_vllm
       ```

The vLLM server handles all GPU acceleration, audio preprocessing, and
model inference efficiently using paged attention and optimized kernels.
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


class VoxtralVLLMEngine(TranscriptionEngine):
    """
    vLLM-backed Voxtral engine using OpenAI-compatible API.

    This engine delegates all heavy computation to a vLLM server,
    which provides optimal GPU utilization with paged attention,
    tensor parallelism, and efficient audio processing.
    """

    def __init__(self, config: EngineConfig) -> None:
        self.config = config
        self.model_name = normalize_model_name("voxtral_vllm", config.model_name)

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
            if self.model_name != served_model:
                logger.warning(
                    f"Requested model '{self.model_name}' differs from vLLM served model '{served_model}'. "
                    f"Using served model."
                )
                self.model_name = served_model

        except Exception as exc:
            logger.debug(f"Could not query vLLM models endpoint: {exc}")
            # Continue with configured model name - vLLM might be starting up

    def start(self, options: TranscriptionOptions) -> None:
        """Initialize the engine with session-specific options."""
        self._options = options
        self._buffer.clear()
        self._segments.clear()
        self._lazy_client()

    def push_audio(self, pcm16: bytes, timestamp_ms: int) -> None:
        """Append raw 16 kHz mono PCM16 audio to the internal buffer."""
        self._buffer.extend(pcm16)

    def _encode_audio_base64(self, pcm16_bytes: bytes) -> str:
        """Convert PCM16 audio to base64-encoded WAV for the API."""
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

        # Encode as base64
        wav_buffer.seek(0)
        return base64.b64encode(wav_buffer.read()).decode('utf-8')

    def flush(self) -> None:
        """Force processing of whatever is currently buffered."""
        if not self._buffer:
            return

        import numpy as np

        audio_bytes = bytes(self._buffer)
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
        duration_s = len(audio_np) / self._sample_rate

        # Encode audio as base64 WAV
        audio_base64 = self._encode_audio_base64(audio_bytes)

        # Build the transcription request using Voxtral's chat format
        language = self._options.language if self._options else "en"

        # Voxtral uses a specific message format for transcription
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "audio",
                        "audio": {
                            "base64": audio_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": f"Transcribe this audio. Language: {language}. Output only the transcription, no explanations.",
                    },
                ],
            }
        ]

        # Get generation parameters
        params = self._options.params if self._options else {}
        max_tokens = int(params.get("max_new_tokens", "2048") or "2048")
        temperature = float(params.get("temperature", "0") or "0")

        if self._client is None:
            raise EngineError("vLLM client not initialized - call start() first")

        try:
            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature if temperature > 0 else None,
            )

            transcription = response.choices[0].message.content.strip()

            if transcription:
                self._segments.append(TranscriptSegment(
                    text=transcription,
                    start_s=0.0,
                    end_s=duration_s,
                    language=language,
                    confidence=1.0,
                ))

        except Exception as exc:
            logger.error(f"vLLM transcription failed: {exc}")
            raise EngineError(f"vLLM transcription failed: {exc}") from exc

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
