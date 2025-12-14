"""
Vociferous - Transcription module using faster-whisper.

This module provides the core speech-to-text functionality using OpenAI's
Whisper model via the faster-whisper library (CTranslate2 backend).

Architecture Overview:
----------------------
```
Audio Data (int16 numpy array)
        │
        ▼
┌─────────────────────┐
│   transcribe()      │  Entry point, handles type conversion
├─────────────────────┤
│ • Convert int16→f32 │  Whisper expects float32 normalized audio
│ • Apply VAD filter  │  Voice Activity Detection for clean output
│ • Combine segments  │  Whisper outputs in chunks, we join them
└────────┬────────────┘
         ▼
┌─────────────────────┐
│ post_process()      │  Add trailing space, strip whitespace, etc.
└─────────────────────┘
```

Why faster-whisper?
-------------------
The original OpenAI Whisper uses PyTorch, which is ~2GB and slower.
faster-whisper uses CTranslate2, providing:

- **4x faster inference** on CPU
- **2x faster on GPU** with less VRAM
- **Smaller memory footprint** (quantization support)
- **Same accuracy** (converted from original weights)

GPU vs CPU Selection:
---------------------
The module attempts CUDA first, then falls back to CPU. Key considerations:

- `float16`: Requires CUDA GPU with tensor cores (RTX series)
- `int8`: Forces CPU (quantized for size/speed tradeoff)
- `auto`: Try CUDA, CTranslate2 handles fallback

TYPE_CHECKING Pattern:
----------------------
```python
if TYPE_CHECKING:
    from faster_whisper import WhisperModel
```

This is a common pattern for heavy imports. During type checking (mypy, IDE),
the import runs for type hints. At runtime, it's skipped, deferring the
actual import to when the model is needed. This speeds up module load time.

Python 3.12+ Features:
----------------------
- Union type hints with `|` syntax (`str | None` instead of `Optional[str]`)
- Generic type hints (`NDArray[np.int16]` without `from __future__`)
- Match/case for device/compute_type combinations
"""
import logging
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from utils import ConfigManager

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


def create_local_model() -> 'WhisperModel':
    """
    Create and configure a faster-whisper model instance.

    This factory function handles the complexity of model initialization:
    device selection, compute type validation, and graceful fallback.

    Model Selection Logic:
    ----------------------
    The match/case statement handles device/compute combinations:

    ```python
    match (device, compute_type):
        case ('auto', _):     # Any compute type with auto device
            device = 'cuda'   # CTranslate2 will fallback if needed
        case (_, 'int8'):     # int8 quant on any device
            device = 'cpu'    # int8 doesn't benefit from GPU
    ```

    Using tuple matching `(device, compute_type)` lets us express complex
    conditional logic declaratively rather than nested if/elif chains.

    Available Models:
    -----------------
    - `tiny`, `base`, `small`, `medium`, `large-v3`: Standard sizes
    - `distil-large-v3`: Distilled version, nearly same accuracy, 2x faster

    Compute Types:
    --------------
    - `float16`: GPU only, fastest, requires 16-bit support
    - `float32`: Universal, slower but most compatible
    - `int8`: Quantized, smallest memory, CPU-focused

    Fallback Strategy:
    ------------------
    If CUDA initialization fails (driver issues, OOM, etc.), we catch the
    exception and retry with CPU. This provides resilience without requiring
    user intervention.

    Cache Optimization:
    -------------------
    The function first attempts to load from local cache (local_files_only=True)
    to avoid unnecessary HTTP requests to HuggingFace. Only if the model isn't
    cached will it download with network access.

    Returns:
        Configured WhisperModel ready for transcription

    Example:
        >>> model = create_local_model()  # Uses config settings
        >>> segments, _ = model.transcribe(audio_array)
    """
    from faster_whisper import WhisperModel

    ConfigManager.console_print('Loading Whisper model...')

    model_options = ConfigManager.get_config_section('model_options')
    model_name: str = model_options.get('model', 'distil-large-v3')
    device: str = model_options.get('device', 'auto')
    compute_type: str = model_options.get('compute_type', 'float16')

    # Handle device selection using match/case
    match (device, compute_type):
        case ('auto', _):
            device = 'cuda'  # Try CUDA first, faster-whisper will fall back to CPU
        case (_, 'int8'):
            device = 'cpu'
            ConfigManager.console_print('Using int8 quantization, forcing CPU.')

    # Try loading from cache first to avoid unnecessary HTTP requests
    model = None
    try:
        # Attempt local-only load (no network)
        model = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
            local_files_only=True
        )
        ConfigManager.console_print(
            f'Model loaded from cache: {model_name} on {device}'
        )
    except Exception:
        # Model not in cache, download it
        ConfigManager.console_print(f'Model not cached, downloading {model_name}...')
        try:
            model = WhisperModel(model_name, device=device, compute_type=compute_type)
            ConfigManager.console_print(
                f'Model downloaded: {model_name} on {device}'
            )
        except Exception as e:
            logger.warning(f'Error loading model on {device}: {e}')
            ConfigManager.console_print('Falling back to CPU...')
            model = WhisperModel(model_name, device='cpu', compute_type=compute_type)
            ConfigManager.console_print(f'Model loaded: {model_name} on CPU')

    return model


def transcribe(
    audio_data: NDArray[np.int16] | None,
    local_model: 'WhisperModel | None' = None
) -> str:
    """
    Transcribe audio data to text using faster-whisper.

    This is the main entry point for speech-to-text conversion. It handles
    audio format conversion, model invocation, and post-processing.

    Audio Format Conversion:
    ------------------------
    Input: int16 samples (range: -32768 to 32767)
    Output needed: float32 samples (range: -1.0 to 1.0)

    ```python
    audio_float = audio_data.astype(np.float32) / 32768.0
    ```

    Why this conversion? Audio hardware and sounddevice output int16,
    but neural networks expect normalized float input. Dividing by 32768
    (max int16 value) normalizes to [-1, 1] range.

    VAD Filter:
    -----------
    `vad_filter=True` enables Silero VAD (Voice Activity Detection) inside
    faster-whisper. This:
    - Skips silence regions (faster processing)
    - Reduces hallucinations (Whisper sometimes generates text for silence)
    - Improves punctuation by detecting speech boundaries

    Segment Concatenation:
    ----------------------
    Whisper outputs transcription in segments (typically sentence-ish chunks).
    We use a generator expression to efficiently join them:

    ```python
    ''.join(segment.text for segment in segments)
    ```

    Generator expressions are memory-efficient - we don't build a list first.

    Args:
        audio_data: Numpy array of int16 audio samples (16kHz mono expected)
        local_model: Pre-loaded WhisperModel (optional, creates new if None)

    Returns:
        Transcribed text after post-processing (trailing space, etc.)

    Example:
        >>> import numpy as np
        >>> audio = np.random.randint(-32768, 32767, 16000, dtype=np.int16)
        >>> text = transcribe(audio, model)
        >>> print(text)  # "Hello world "
    """
    if audio_data is None:
        return ''

    if local_model is None:
        local_model = create_local_model()

    model_options = ConfigManager.get_config_section('model_options')
    language: str | None = model_options.get('language', 'en') or None

    # Convert int16 to float32 (required by faster-whisper)
    audio_float: NDArray[np.float32] = audio_data.astype(np.float32) / 32768.0

    # Transcribe with VAD for cleaner output
    segments, _ = local_model.transcribe(
        audio=audio_float,
        language=language,
        vad_filter=True,
    )

    # Combine segments using generator expression
    transcription = ''.join(segment.text for segment in segments).strip()

    return post_process_transcription(transcription)


def post_process_transcription(transcription: str | None) -> str:
    """
    Apply user-configured post-processing to transcription output.

    Post-processing handles the "last mile" of transcription - making the
    raw model output suitable for the user's specific use case.

    Current Processing Steps:
    -------------------------
    1. **Strip whitespace**: Remove leading/trailing spaces from Whisper output
    2. **Add trailing space**: If enabled, add space after transcription
       (useful when typing into text fields - natural word separation)

    Why Trailing Space?
    -------------------
    When you're dictating into a text field, you typically want a space after
    each transcription so the next word doesn't run together:

    Without: "Hello""World" → "HelloWorld"
    With:    "Hello " + "World " → "Hello World "

    This is configurable because some use cases (like code comments) might
    not want automatic spacing.

    Guard Clause Pattern:
    ---------------------
    ```python
    if not transcription:
        return ''
    ```

    Early return for falsy input (None, empty string) prevents NoneType
    errors and makes the happy path code cleaner.

    Args:
        transcription: Raw transcription text from Whisper (may be None)

    Returns:
        Processed transcription ready for output
    """
    if not transcription:
        return ''

    result = transcription.strip()

    output_options = ConfigManager.get_config_section('output_options')

    if output_options.get('add_trailing_space', True):
        result += ' '

    return result
