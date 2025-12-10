"""Test FFmpegCondenser with real VAD timestamps."""

from pathlib import Path
import time

print("=" * 60)
print("TEST: FFmpegCondenser Pipeline")
print("=" * 60)

audio_path = Path("samples/ASR_Test.flac")
output_dir = Path("debug_output")
output_dir.mkdir(exist_ok=True)

if not audio_path.exists():
    print(f"\u274c Test file not found: {audio_path}")
    exit(1)

# Step 1: Get VAD timestamps
print("\n[1/2] Running SileroVAD...")
try:
    from vociferous.audio.silero_vad import SileroVAD

    vad = SileroVAD(device="cpu")

    start = time.time()
    timestamps = vad.detect_speech(audio_path, save_json=False)
    elapsed = time.time() - start

    print(f"\u2705 VAD completed in {elapsed:.2f}s")
    print(f"   Detected {len(timestamps)} segments")

    if len(timestamps) == 0:
        print("\u274c No speech detected, cannot test condenser")
        exit(1)

except Exception as e:
    print(f"\u274c VAD failed: {e}")
    exit(1)

# Step 2: Run condenser
print("\n[2/2] Running FFmpegCondenser...")
try:
    from vociferous.audio.ffmpeg_condenser import FFmpegCondenser

    condenser = FFmpegCondenser()

    start = time.time()
    output_files = condenser.condense(
        audio_path,
        timestamps,
        output_dir=output_dir,
        max_duration_minutes=30,
        min_gap_for_split_s=5.0,
        boundary_margin_s=1.0,
    )
    elapsed = time.time() - start

    print(f"\u2705 Condenser completed in {elapsed:.2f}s")
    print(f"   Generated {len(output_files)} file(s)")

    for i, f in enumerate(output_files):
        if not f.exists():
            print(f"\u274c Output file does not exist: {f}")
            exit(1)

        size_kb = f.stat().st_size / 1024
        print(f"   File {i+1}: {f.name} ({size_kb:.2f} KB)")

    print("\n\u2705 SUCCESS: Condenser pipeline works")
    print(f"\nOutput files in: {output_dir}/")
    print("Listen to these files to verify audio quality:")
    for f in output_files:
        print(f"  - {f}")

except Exception as e:
    print(f"\n\u274c Condenser failed: {e}")
    import traceback

    traceback.print_exc()
    exit(1)
