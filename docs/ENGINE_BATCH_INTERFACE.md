# Engine Batch Interface Usage Guide

## Overview

The refactored engine architecture provides a new batch processing interface that's simpler and eliminates the overlapping segments issue. This guide shows how to use it.

## New Batch Interface

Both `WhisperTurboEngine` and `VoxtralLocalEngine` now have a `transcribe_file()` method:

```python
def transcribe_file(
    self, 
    audio_path: Path, 
    options: TranscriptionOptions
) -> list[TranscriptSegment]:
    """Transcribe entire audio file in one batch operation."""
```

## Example: Direct Engine Usage with SegmentArbiter

```python
from pathlib import Path
from vociferous.engines import WhisperTurboEngine
from vociferous.domain.model import EngineConfig, TranscriptionOptions
from vociferous.app.arbiter import SegmentArbiter

# 1. Configure engine
config = EngineConfig(
    model_name="tiny",
    device="cpu",
    compute_type="int8",
)

# 2. Create engine
engine = WhisperTurboEngine(config)

# 3. Set transcription options
options = TranscriptionOptions(
    language="en",
    beam_size=1,
)

# 4. Transcribe preprocessed audio file
# Note: Audio should already be decoded and condensed (16kHz mono PCM WAV)
audio_path = Path("samples/ASR_Test_30s_condensed.wav")
raw_segments = engine.transcribe_file(audio_path, options)

# 5. Clean up segments with SegmentArbiter
arbiter = SegmentArbiter(
    min_segment_duration_s=1.0,
    min_segment_words=4,
    hard_break_silence_s=1.5,
    soft_break_silence_s=0.7,
)
clean_segments = arbiter.arbitrate(raw_segments)

# 6. Output results
for seg in clean_segments:
    print(f"{seg.start_s:.2f}-{seg.end_s:.2f}: {seg.text}")
```

## Key Improvements

### Before Refactoring
- ❌ Internal VAD in engine duplicated preprocessing VAD
- ❌ Sliding window overlap caused duplicate segments
- ❌ Complex state management
- ❌ Output: `36.48-38.40: 14, 15, 16, 16, 16, 16, 16...` (repeating)

### After Refactoring
- ✅ Single VAD pass in preprocessing
- ✅ No sliding window overlap
- ✅ Simple batch processing
- ✅ SegmentArbiter deduplicates and merges
- ✅ Output: Clean, non-overlapping segments

## Legacy Streaming Interface (Deprecated)

The old streaming interface (`start()`, `push_audio()`, `flush()`, `poll_segments()`) may still exist in some engines for backward compatibility during the refactoring transition (see issue #21), but **batch processing is the recommended and supported approach** for all use cases. The streaming interface adds unnecessary complexity and is being phased out.

**Use the batch interface (`transcribe_file()`) for all new code.**

## SegmentArbiter Configuration

```python
arbiter = SegmentArbiter(
    min_segment_duration_s=1.0,      # Minimum duration for standalone segment
    min_segment_words=4,               # Minimum word count for standalone segment
    hard_break_silence_s=1.5,         # Silence gap that forces segment boundary
    soft_break_silence_s=0.7,         # Silence gap for soft breaks (respects punctuation)
)
```

The arbiter will:
1. Remove duplicate overlapping text
2. Merge tiny fragments into adjacent segments
3. Respect punctuation boundaries (merge mid-phrase segments)
4. Ensure no overlaps in final output

## Benefits

1. **No Duplicate Segments**: SegmentArbiter removes overlapping text
2. **Clean Boundaries**: Respects sentence punctuation and natural breaks
3. **Simpler Code**: Direct file processing, no streaming state
4. **Better Performance**: Single pass through audio
5. **Easier Testing**: Deterministic output, no timing dependencies
