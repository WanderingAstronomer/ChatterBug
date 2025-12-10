"""Test if VadWrapper is fundamentally broken or just misconfigured."""

import numpy as np
import signal
import time


def timeout_handler(signum, frame):
    raise TimeoutError("Operation hung for >5 seconds")


def make_speech_like_chunk(sample_rate: int, seconds: float, seed: int) -> np.ndarray:
    """Create a speech-ish waveform that Silero VAD will flag as voice."""
    rng = np.random.default_rng(seed)
    samples = int(sample_rate * seconds)
    t = np.linspace(0, seconds, samples, endpoint=False)

    # Band-limited noise plus a few low formants, shaped with an envelope.
    noise = rng.normal(0, 0.2, size=samples)
    window = np.ones(100) / 100  # simple smoothing filter
    band = np.convolve(noise, window, mode="same")
    formants = (
        0.4 * np.sin(2 * np.pi * 120 * t)
        + 0.3 * np.sin(2 * np.pi * 220 * t)
        + 0.2 * np.sin(2 * np.pi * 310 * t)
    )
    envelope = np.clip(np.sin(np.pi * np.linspace(0, 1, samples)) * 1.3, 0, 1)
    speech = (band + formants) * envelope
    return np.clip(speech * 28000, -32768, 32767).astype(np.int16)


print("=" * 60)
print("TEST 1: VadWrapper Initialization")
print("=" * 60)

try:
    from vociferous.audio.vad import VadWrapper

    vad = VadWrapper(sample_rate=16000, device="cpu")
    print("\u2705 VadWrapper created")
    print(f"   Sample rate: {vad.sample_rate}")
    print(f"   Device: {vad.device}")
    print(f"   Enabled: {vad._enabled}")
except Exception as e:
    print(f"\u274c VadWrapper creation failed: {e}")
    import traceback

    traceback.print_exc()
    exit(1)

print("\n" + "=" * 60)
print("TEST 2: Generate Synthetic Audio (Speech-like)")
print("=" * 60)

# Create 2 seconds:  1s speech, 0.5s silence, 0.5s speech
sample_rate = 16000
silence_samples = 8000  # 0.5 seconds

# Speech-ish waveforms that Silero VAD will register
speech1 = make_speech_like_chunk(sample_rate, 1.0, seed=0)
speech2 = make_speech_like_chunk(sample_rate, 0.5, seed=1)
silence = np.zeros(silence_samples, dtype=np.int16)

audio = np.concatenate([speech1, silence, speech2])
audio_bytes = audio.tobytes()

print(f"\u2705 Generated {len(audio_bytes)} bytes of synthetic audio")
print(f"   Duration: {len(audio) / sample_rate:.2f} seconds")
print("   Structure: 1s speech -> 0.5s silence -> 0.5s speech")

print("\n" + "=" * 60)
print("TEST 3: Call speech_spans() on Synthetic Audio")
print("=" * 60)

try:
    start = time.time()

    spans = vad.speech_spans(
        audio_bytes,
        threshold=0.2,
        min_silence_ms=100,
        min_speech_ms=100,
    )

    elapsed = time.time() - start

    print(f"\u2705 speech_spans() returned in {elapsed:.2f}s")
    print(f"   Type: {type(spans)}")
    print(f"   Length: {len(spans)}")
    print(f"   Content: {spans}")

    if len(spans) == 0:
        print("\n\u274c PROBLEM: No spans detected in synthetic speech audio!")
        print("   VadWrapper is broken or Silero model isn't loaded.")
        exit(1)
    else:
        print("\n\u2705 SUCCESS: VadWrapper detected speech spans")
        for i, (start_sample, end_sample) in enumerate(spans):
            duration = (end_sample - start_sample) / sample_rate
            print(f"   Span {i+1}: {start_sample} -> {end_sample} ({duration:.2f}s)")

except Exception as e:
    print(f"\u274c speech_spans() failed: {e}")
    import traceback

    traceback.print_exc()
    exit(1)

print("\n" + "=" * 60)
print("TEST 4: Call speech_spans() with TIMEOUT (Hang Detection)")
print("=" * 60)

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(5)  # 5-second timeout

try:
    spans2 = vad.speech_spans(audio_bytes, threshold=0.2)
    signal.alarm(0)  # Cancel alarm
    print(f"\u2705 No hang detected, returned {len(spans2)} spans")
except TimeoutError as e:
    signal.alarm(0)
    print(f"\u274c HANG DETECTED: {e}")
    print("   VadWrapper.speech_spans() is blocking indefinitely")
    exit(1)
except Exception as e:
    signal.alarm(0)
    print(f"\u274c Error: {e}")
    exit(1)

print("\n" + "=" * 60)
print("SUMMARY:  VadWrapper is functional")
print("=" * 60)
