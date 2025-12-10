"""Test if FfmpegDecoder can decode your test file."""

from pathlib import Path
import time

print("=" * 60)
print("TEST:  Decode ASR_Test.flac")
print("=" * 60)

audio_path = Path("samples/ASR_Test.flac")

if not audio_path.exists():
    print(f"\u274c Test file not found: {audio_path}")
    exit(1)

print(f"\u2705 Found test file: {audio_path}")
print(f"   Size: {audio_path.stat().st_size / 1024 / 1024:.2f} MB")

try:
    from vociferous.audio.decoder import FfmpegDecoder

    decoder = FfmpegDecoder()

    start = time.time()
    decoded = decoder.decode(str(audio_path))
    elapsed = time.time() - start

    print(f"\n\u2705 Decoding succeeded in {elapsed:.2f}s")
    print(f"   Sample rate: {decoded.sample_rate}")
    print(f"   Channels: {decoded.channels}")
    print(f"   Duration: {decoded.duration_s:.2f}s")
    print(f"   Samples: {len(decoded.samples)} bytes")

    expected_bytes = int(decoded.sample_rate * decoded.channels * decoded.duration_s * 2)
    print(f"   Expected bytes: {expected_bytes}")

    # Sanity check
    if len(decoded.samples) == 0:
        print("\n\u274c PROBLEM:  Decoded audio is empty!")
        exit(1)

    if abs(len(decoded.samples) - expected_bytes) > expected_bytes * 0.1:
        print("\n\u26a0\ufe0f WARNING: Decoded size differs from expected by >10%")

    print("\n\u2705 Decoder works correctly")

except Exception as e:
    print(f"\n\u274c Decoding failed: {e}")
    import traceback

    traceback.print_exc()
    exit(1)
