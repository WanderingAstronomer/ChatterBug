"""Minimal audio capture stub for ChatterBug.

Provides `record(stop_event=None, max_sec=60.0) -> (wav_bytes, duration_s)`.
This implementation uses `sounddevice` and `soundfile` when available; otherwise
it returns empty bytes so the app remains importable on systems without audio.
"""
import io
import time
import threading
from typing import Optional, Tuple

try:
    import numpy as np
    import sounddevice as sd
    import soundfile as sf
    _HAS_AUDIO = True
except Exception:
    _HAS_AUDIO = False

SAMPLERATE = 16000
CHANNELS = 1

def record(stop_event: Optional[threading.Event] = None, max_sec: float = 60.0) -> Tuple[bytes, float]:
    if not _HAS_AUDIO:
        return b"", 0.0

    frames = []

    def callback(indata, frames_count, time_info, status):
        frames.append(indata.copy())

    with sd.InputStream(samplerate=SAMPLERATE, channels=CHANNELS, callback=callback):
        start = time.time()
        while True:
            if stop_event and stop_event.is_set():
                break
            if (time.time() - start) >= float(max_sec):
                break
            time.sleep(0.05)

    if not frames:
        return b"", 0.0

    data = np.concatenate(frames, axis=0)
    duration = data.shape[0] / float(SAMPLERATE)
    bio = io.BytesIO()
    sf.write(bio, data, SAMPLERATE, format="WAV", subtype="PCM_16")
    return bio.getvalue(), duration
