"""Test SileroVAD on actual audio file with timeout protection."""

from pathlib import Path
import signal
import time


def timeout_handler(signum, frame):
    raise TimeoutError("Operation hung for >30 seconds")


print("=" * 60)
print("TEST: SileroVAD on ASR_Test.flac (WITH TIMEOUT)")
print("=" * 60)

audio_path = Path("samples/ASR_Test.flac")

if not audio_path.exists():
    print(f"\u274c File not found: {audio_path}")
    exit(1)

try:
    from vociferous.audio.silero_vad import SileroVAD

    vad = SileroVAD(device="cpu")  # Use CPU to avoid CUDA issues
    print("\u2705 SileroVAD created")
except Exception as e:
    print(f"\u274c SileroVAD creation failed: {e}")
    import traceback

    traceback.print_exc()
    exit(1)

# Set 30-second timeout
signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(30)

try:
    start = time.time()

    timestamps = vad.detect_speech(audio_path, save_json=True)

    signal.alarm(0)  # Cancel timeout
    elapsed = time.time() - start

    print(f"\n\u2705 detect_speech() completed in {elapsed:.2f}s")
    print(f"   Returned {len(timestamps)} segments")

    if len(timestamps) == 0:
        print("\n\u274c PROBLEM: Zero segments detected!")
        print("   Possible causes:")
        print("   1. VadWrapper.speech_spans() returns empty list")
        print("   2. Silero model not loaded")
        print("   3. Audio decoding failed silently")
        exit(1)

    print("\n\u2705 SUCCESS: Speech detected")

    # Show first 5 segments
    print("\nFirst 5 segments:")
    for i, ts in enumerate(timestamps[:5]):
        duration = ts["end"] - ts["start"]
        print(f"  {i+1}. {ts['start']:7.2f}s - {ts['end']:7.2f}s (duration: {duration:5.2f}s)")

    # Calculate total speech duration
    total_speech = sum(ts["end"] - ts["start"] for ts in timestamps)
    print(f"\nTotal speech duration: {total_speech:.2f}s")

    # Check for JSON cache
    cache_file = audio_path.with_name(f"{audio_path.stem}_vad_timestamps.json")
    if cache_file.exists():
        print(f"\u2705 JSON cache created: {cache_file}")
    else:
        print(f"\u26a0\ufe0f JSON cache NOT created (expected at {cache_file})")

except TimeoutError:
    signal.alarm(0)
    print("\n\u274c TIMEOUT: detect_speech() hung for >30 seconds")
    print("   This confirms VadWrapper has a blocking bug")
    exit(1)
except Exception as e:
    signal.alarm(0)
    print(f"\n\u274c Error: {e}")
    import traceback

    traceback.print_exc()
    exit(1)

print("\n" + "=" * 60)
print("SUMMARY: SileroVAD pipeline is functional")
print("=" * 60)
