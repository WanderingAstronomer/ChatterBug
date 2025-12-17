"""
Audio recording and transcription thread for Vociferous.

Captures audio from microphone, applies Voice Activity Detection (VAD),
and sends audio to the Whisper transcription engine via QThread.
"""
import logging
import time
from queue import Empty, Queue
from typing import TYPE_CHECKING

import numpy as np
import sounddevice as sd
import webrtcvad
from numpy.typing import NDArray
from PyQt5.QtCore import QMutex, QThread, pyqtSignal

from transcription import transcribe
from utils import ConfigManager

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


class ResultThread(QThread):
    """
    QThread for audio recording and transcription.

    Pipeline: capture audio → VAD filtering → Whisper transcription → emit result.
    Signals cross thread boundaries safely via Qt's meta-object system.
    """

    statusSignal = pyqtSignal(str)
    resultSignal = pyqtSignal(str)

    def __init__(self, local_model: 'WhisperModel | None' = None) -> None:
        """Initialize the ResultThread."""
        super().__init__()
        self.local_model = local_model
        self.is_recording: bool = False
        self.is_running: bool = True
        self.sample_rate: int | None = None
        self.mutex = QMutex()

    def stop_recording(self) -> None:
        """Stop the current recording session."""
        self.mutex.lock()
        self.is_recording = False
        self.mutex.unlock()

    def stop(self) -> None:
        """Stop the entire thread execution."""
        self.mutex.lock()
        self.is_running = False
        self.mutex.unlock()
        self.statusSignal.emit('idle')
        self.wait()

    def run(self) -> None:
        """
        Main thread execution: record audio, transcribe, emit result.
        
        Always use start() to spawn thread - never call run() directly.
        Wrapped in try/finally to ensure cleanup on error.
        """
        try:
            if not self.is_running:
                return

            self.mutex.lock()
            self.is_recording = True
            self.mutex.unlock()

            self.statusSignal.emit('recording')
            ConfigManager.console_print('Recording...')
            audio_data = self._record_audio()

            if not self.is_running:
                return

            if audio_data is None:
                self.statusSignal.emit('idle')
                return

            self.statusSignal.emit('transcribing')
            ConfigManager.console_print('Transcribing...')

            # Time the transcription process
            start_time = time.perf_counter()
            result = transcribe(audio_data, self.local_model)
            elapsed = time.perf_counter() - start_time

            ConfigManager.console_print(
                f'Transcription completed in {elapsed:.2f}s: {result}'
            )

            if not self.is_running:
                return

            self.statusSignal.emit('idle')
            self.resultSignal.emit(result)

        except Exception:
            logger.exception("Error during recording/transcription")
            self.statusSignal.emit('error')
            self.resultSignal.emit('')
        finally:
            self.stop_recording()

    def _record_audio(self) -> NDArray[np.int16] | None:
        """
        Record audio from microphone with Voice Activity Detection.
        
        Skips first 150ms to avoid hotkey press sounds.
        Uses WebRTC VAD to auto-stop when silence is detected.
        Returns None if recording is too short.
        """
        recording_options = ConfigManager.get_config_section('recording_options')
        self.sample_rate = recording_options.get('sample_rate') or 16000
        frame_duration_ms = 30  # WebRTC VAD frame duration
        frame_size = int(self.sample_rate * (frame_duration_ms / 1000.0))
        silence_duration_ms = recording_options.get('silence_duration') or 900
        silence_frames = int(silence_duration_ms / frame_duration_ms)

        # 150ms delay to avoid capturing key press sounds
        initial_frames_to_skip = int(0.15 * self.sample_rate / frame_size)

        # Create VAD for voice activity detection modes
        recording_mode = recording_options.get('recording_mode') or 'continuous'
        vad = None
        speech_detected = False
        silent_frame_count = 0

        if recording_mode in ('voice_activity_detection', 'continuous'):
            vad = webrtcvad.Vad(2)  # Aggressiveness: 0-3 (higher = more aggressive)

        # Thread-safe queue for audio callback data
        audio_queue: Queue[NDArray[np.int16]] = Queue()
        recording: list[np.int16] = []

        def audio_callback(indata, frames, time_info, status) -> None:
            if status:
                logger.debug(f"Audio callback status: {status}")
            # Copy audio data - numpy arrays share memory
            audio_queue.put(indata[:, 0].copy())

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype='int16',
            blocksize=frame_size,
            callback=audio_callback
        ):
            while self.is_running and self.is_recording:
                try:
                    frame = audio_queue.get(timeout=0.1)
                except Empty:
                    continue

                if len(frame) < frame_size:
                    continue

                recording.extend(frame)

                # Skip initial frames to avoid key press sounds
                if initial_frames_to_skip > 0:
                    initial_frames_to_skip -= 1
                    continue

                if vad:
                    is_speech = vad.is_speech(frame.tobytes(), self.sample_rate)
                    match (is_speech, speech_detected):
                        case (True, False):
                            ConfigManager.console_print("Speech detected.")
                            speech_detected = True
                            silent_frame_count = 0
                        case (True, True):
                            silent_frame_count = 0
                        case (False, _):
                            silent_frame_count += 1

                    if speech_detected and silent_frame_count > silence_frames:
                        break

        audio_data = np.array(recording, dtype=np.int16)
        duration = len(audio_data) / self.sample_rate
        min_duration_ms = recording_options.get('min_duration') or 100

        ConfigManager.console_print(
            f'Recording finished: {audio_data.size} samples, {duration:.2f}s'
        )

        if (duration * 1000) < min_duration_ms:
            ConfigManager.console_print('Discarded: too short')
            return None

        return audio_data
