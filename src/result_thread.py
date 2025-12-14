"""
Audio recording and transcription thread for Vociferous.

This module implements the core recording pipeline using Qt's threading model.
It captures audio from the microphone, applies Voice Activity Detection (VAD),
and sends the audio to the transcription engine.

Architecture Overview:
----------------------
```
┌────────────────────────────────────────────────────────────────┐
│                    ResultThread (QThread)                      │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌─────────────┐   Queue    ┌─────────────────┐                │
│  │ sounddevice │ ────────▶ │  Main Loop      │                │
│  │ callback    │            │  (in run())     │                │
│  │ (OS thread) │            └────────┬────────┘                │
│  └─────────────┘                     │                         │
│                                      ▼                         │
│                           ┌─────────────────┐                  │
│                           │  WebRTC VAD     │                  │
│                           │  (speech detect)│                  │
│                           └────────┬────────┘                  │
│                                    │                           │
│                                    ▼                           │
│                           ┌─────────────────┐                  │
│                           │  transcribe()   │                  │
│                           │  (faster-whisper)│                 │
│                           └────────┬────────┘                  │
│                                    │                           │
│                        pyqtSignal  │                           │
│                                    ▼                           │
│                           ┌─────────────────┐                  │
│                           │  Main Thread    │                  │
│                           │  (UI updates)   │                  │
│                           └─────────────────┘                  │
└────────────────────────────────────────────────────────────────┘
```

Threading Model:
----------------
Audio capture uses THREE threads:
1. **OS Audio Thread**: Calls our callback, fills queue (managed by sounddevice)
2. **QThread (run)**: Pulls from queue, runs VAD, calls transcribe()
3. **Main Thread**: Receives signals, updates UI

The Queue acts as a thread-safe buffer between the OS callback and our
processing loop. This decoupling prevents audio dropouts - the callback
is ultra-fast (just queue.put), while processing can take longer.

Voice Activity Detection (VAD):
-------------------------------
WebRTC VAD analyzes 30ms audio frames to detect speech. This enables:
- **Auto-stop**: Stop recording when user stops speaking
- **Silence trimming**: Don't send silence to Whisper (wastes compute)

VAD modes:
- 0-3 aggressiveness (higher = more aggressive filtering)
- We use 2 as a balance between catching speech and filtering noise

QThread vs threading.Thread:
-----------------------------
QThread integrates with Qt's event system:
- Signals can cross thread boundaries safely
- Automatic cleanup with deleteLater()
- wait() blocks main thread until child finishes
- Event loop can be run in the thread (not used here)

threading.Thread is more lightweight but requires manual synchronization
for communicating back to the main/UI thread.

QMutex for State Protection:
----------------------------
```python
self.mutex.lock()
self.is_recording = False
self.mutex.unlock()
```

The mutex protects `is_running` and `is_recording` flags from race conditions.
Without it, the main thread might set is_recording=False while the worker
thread is checking it, causing undefined behavior.

Python 3.12+ Features:
----------------------
- Match/case for VAD state transitions
- `int | None` union type hints
- `NDArray[np.int16]` generic numpy typing
- `Queue[NDArray[np.int16]]` generic queue typing
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
    QThread subclass for audio recording and transcription.

    This thread runs the complete dictation pipeline:
    1. Capture audio from microphone (via sounddevice)
    2. Apply VAD to detect speech/silence
    3. Send audio to Whisper for transcription
    4. Emit result via Qt signal

    Why QThread?
    ------------
    - **Signal/Slot integration**: Signals cross thread boundaries safely
    - **Qt event loop compatibility**: Works with QApplication
    - **Lifecycle management**: wait(), quit(), deleteLater()

    Class Attributes (Signals):
    ---------------------------
    Signals are defined at class level because Qt's meta-object system
    processes them at class creation time. They're shared by all instances
    but each connection is instance-specific.

    ```python
    statusSignal = pyqtSignal(str)  # Class attribute
    self.statusSignal.emit('recording')  # Instance method
    ```

    Instance Attributes:
    --------------------
        local_model: Pre-loaded Whisper model (passed in, not created)
        is_recording: Currently capturing audio? (mutex-protected)
        is_running: Thread should continue? (mutex-protected)
        sample_rate: Audio sample rate in Hz (typically 16000)
        mutex: QMutex for thread-safe state access
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
        Main execution method - called when thread.start() is invoked.

        This overrides QThread.run() to provide our custom logic.
        NEVER call run() directly - always use start() which spawns
        the thread and then calls run() in the new thread context.

        Pipeline:
        ---------
        1. Emit 'recording' status
        2. Call _record_audio() (blocks until recording complete)
        3. Emit 'transcribing' status
        4. Call transcribe() with audio data
        5. Emit 'idle' status and result

        Error Handling:
        ---------------
        The entire method is wrapped in try/except/finally:
        - Exceptions: Log, emit 'error' status, emit empty result
        - Finally: Always call stop_recording() to clean up state

        This ensures the thread never leaves the app in a broken state,
        even if transcription fails (network, OOM, etc.).
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

        Recording Flow:
        ---------------
        1. **Setup**: Create sounddevice InputStream with callback
        2. **Capture**: Callback puts frames into Queue (OS thread)
        3. **Process**: Main loop pulls frames, runs VAD (this thread)
        4. **Stop**: When silence detected or is_recording becomes False

        Initial Frame Skip:
        -------------------
        We skip 150ms of audio at the start to avoid capturing the
        keyboard sound from pressing the hotkey. Without this, transcription
        often starts with "click" or similar.

        VAD State Machine:
        ------------------
        Using match/case for clean state transitions:

        ```python
        match (is_speech, speech_detected):
            case (True, False):   # First speech frame
                speech_detected = True
            case (True, True):    # Continuing speech
                silent_frame_count = 0
            case (False, _):      # Silence (any prior state)
                silent_frame_count += 1
        ```

        When silent_frame_count exceeds threshold, recording stops.

        Audio Callback Pattern:
        -----------------------
        ```python
        def audio_callback(indata, frames, time_info, status):
            audio_queue.put(indata[:, 0].copy())
        ```

        - `indata[:, 0]`: First channel only (mono)
        - `.copy()`: CRITICAL - sounddevice reuses the buffer!

        Without .copy(), the queue would contain views of a buffer that
        gets overwritten on each callback. This is a common sounddevice gotcha.

        Returns:
            Numpy array of int16 samples, or None if too short to transcribe
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
