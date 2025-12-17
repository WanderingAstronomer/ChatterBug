"""
Transcription module using faster-whisper.

Provides speech-to-text via OpenAI Whisper (CTranslate2 backend).
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
    
    Tries CUDA first, falls back to CPU on failure.
    Loads from cache when available to avoid HTTP requests.
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
        case ('cpu', 'float16'):
            # float16 doesn't work on CPU, downgrade to float32
            compute_type = 'float32'
            ConfigManager.console_print('float16 not supported on CPU, using float32 instead.')
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
    
    Converts int16 to float32, runs VAD-filtered transcription,
    then post-processes the result.
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
    """Apply user-configured post-processing (strip whitespace, add trailing space)."""
    if not transcription:
        return ''

    result = transcription.strip()

    output_options = ConfigManager.get_config_section('output_options')

    if output_options.get('add_trailing_space', True):
        result += ' '

    return result
