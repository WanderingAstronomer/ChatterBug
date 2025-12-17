# Audio Recording

The audio recording system captures microphone input with Voice Activity Detection.

## Overview

```
Microphone → sounddevice → VAD Filter → Audio Buffer → Whisper
```

## Components

### sounddevice

Low-level audio capture using PortAudio:

```python
with sd.InputStream(
    samplerate=16000,
    channels=1,
    dtype='int16',
    blocksize=480,  # 30ms frames
    callback=audio_callback
):
    # Recording active
```

### Voice Activity Detection (WebRTC VAD)

Filters out silence to improve transcription quality:

```python
import webrtcvad

vad = webrtcvad.Vad(2)  # Aggressiveness: 0 (lenient) to 3 (aggressive)

# Check each 30ms frame
is_speech = vad.is_speech(frame.tobytes(), sample_rate)
```

## Recording Flow

```
┌────────────────────────────────────────────────────────────┐
│                    ResultThread.run()                       │
├────────────────────────────────────────────────────────────┤
│  1. statusSignal.emit('recording')                          │
│  2. Start InputStream with callback                         │
│  3. Skip first 150ms (avoid hotkey press sounds)            │
│  4. For each frame:                                         │
│     - Check VAD: is_speech(frame)?                          │
│     - If speech detected: reset silence counter             │
│     - If silence: increment counter                         │
│     - If silence > threshold: break                         │
│  5. Stop InputStream                                        │
│  6. Return audio as numpy array                             │
└────────────────────────────────────────────────────────────┘
```

## Audio Format

| Parameter | Value | Reason |
|-----------|-------|--------|
| Sample rate | 16000 Hz | Whisper's native rate |
| Channels | 1 (mono) | Speech recognition is mono |
| Bit depth | 16-bit int | Standard PCM format |
| Frame size | 480 samples | 30ms for VAD compatibility |

## Audio Callback Threading

The sounddevice callback runs in a separate PortAudio thread:

```python
def audio_callback(indata, frames, time_info, status):
    # Called from PortAudio thread - must be fast!
    audio_queue.put(indata[:, 0].copy())  # Thread-safe queue

# Worker thread consumes from queue
while recording:
    frame = audio_queue.get(timeout=0.1)
    # Process frame...
```

## Silence Detection

After speech is detected, silence is tracked:

```python
silence_frames = int(silence_duration_ms / frame_duration_ms)  # e.g., 900ms / 30ms = 30 frames

if speech_detected and silent_frame_count > silence_frames:
    # Stop recording - user finished speaking
    break
```

## Configuration

```yaml
recording_options:
  sample_rate: 16000      # Hz
  silence_duration: 900   # ms of silence before VAD stops
  min_duration: 100       # minimum recording length (ms)
```

## Common Issues

### No audio captured
- Check default input device: `pactl list sources short`
- Verify microphone permissions

### VAD stops too early
- Increase `silence_duration` in config
- Lower VAD aggressiveness (hardcoded, requires code change)

### Hotkey sound in transcription
- The 150ms initial skip should prevent this
- If still occurring, check key release timing
