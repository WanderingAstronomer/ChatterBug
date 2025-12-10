# How It Works

Vociferous uses a clean, modular architecture to transform audio into text. This page explains the technical approach, architecture, and processing pipeline.

## Architecture Overview

Vociferous follows a **ports-and-adapters** (hexagonal) architecture with clear separation of concerns:

```
┌─────────────────────────────────────────┐
│  UI Layer (CLI, GUI, TUI)               │
├─────────────────────────────────────────┤
│  Application Layer                      │
│  - TranscriptionSession                 │
│  - Use Cases (TranscribeFile, etc.)     │
├─────────────────────────────────────────┤
│  Domain Layer                           │
│  - AudioChunk, TranscriptSegment        │
│  - Protocols (AudioSource, Engine)      │
├─────────────────────────────────────────┤
│  Adapters/Infrastructure                │
│  - Engines (Whisper, Voxtral)           │
│  - Audio I/O (File, Microphone)         │
│  - Storage, Config, Hotkeys             │
└─────────────────────────────────────────┘
```

### Layer Responsibilities

**UI Layer**: Entry points for users (CLI commands, GUI windows, TUI interface)
- No direct model or business logic
- Delegates to Application layer

**Application Layer**: Orchestrates use cases and workflows
- `TranscriptionSession`: Coordinates push-based streaming (start → push → flush → poll)
- Validates requests, manages queues, routes outputs
- Maps errors to user-friendly messages

**Domain Layer**: Core business types and contracts
- Pure data structures (frozen dataclasses)
- Protocol definitions (interfaces)
- No dependencies on infrastructure or UI

**Adapters Layer**: Implementations of domain protocols
- Engine adapters (Whisper, Voxtral, Parakeet)
- Audio sources (file, microphone)
- Storage, configuration, hotkeys

## Transcription Pipeline

### Step-by-Step Flow

1. **Audio Input**
   - CLI: File path provided → `FileSource` loads and decodes
   - GUI: File dropped or mic activated → appropriate `AudioSource` initialized
   - Audio decoded to PCM float32 @ 16kHz (Whisper's expected format)

2. **VAD Pre-Processing** (Optional, on by default)
   - Silero VAD detects speech segments
   - Trims silence from beginning/end
   - Reduces processing time and improves accuracy

3. **Engine Processing**
   - Audio chunks pushed to selected engine (push-based, stateful)
   - Engine processes in sliding windows (30s default for Whisper)
   - Segments streamed back as they're ready

4. **Post-Processing**
   - Disfluency cleaning (optional, on by default for Whisper)
   - Removes filler words ("um", "uh", etc.) for cleaner output
   - Polishing via llama.cpp model (optional, requires `[polish]` extra)

5. **Output**
   - Segments assembled into final transcript
   - Written to stdout, file, clipboard, or UI display
   - History saved (optional, configured in settings)

### Pipeline Diagram

```
Audio File/Mic
      ↓
   Decoder (ffmpeg) → PCM 16kHz float32
      ↓
   VAD Filter (Silero) → Speech segments only
      ↓
   Engine (Whisper/Voxtral) → Transcription segments
      ↓
   Post-Processing → Clean disfluencies, polish
      ↓
   Output Sink → File/stdout/clipboard/UI
```

## Engines in Detail

### Whisper Turbo (Default)

**Technology**: OpenAI's Whisper large-v3-turbo via faster-whisper (CTranslate2 backend)

**Characteristics**:
- Optimized variant of Whisper large-v3
- ~8x faster than standard Whisper large
- Maintains high accuracy
- CPU-safe with int8 quantization
- GPU-accelerated with float16 (automatic)

**Processing Mode**:
- Push-based stateful streaming
- 30-second sliding windows with 5-second overlap
- VAD-trimmed chunks for efficiency
- Beam search (configurable, default=1 for speed)

**See Also**: [Engines & Presets](Engines-and-Presets.md)

### Voxtral Local (Optional)

**Technology**: Mistral-based transformer with enhanced punctuation and grammar

**Characteristics**:
- Better punctuation and capitalization than Whisper
- Long-context understanding (up to 128k tokens)
- Slower than Whisper but more natural output
- Requires `[voxtral]` extra installation

**Use Cases**:
- High-quality transcription for publishing
- Long-form content (lectures, interviews)
- When natural punctuation and formatting matter

### Parakeet RNNT (Experimental)

**Technology**: NVIDIA Parakeet RNNT via Riva endpoint

**Characteristics**:
- Streaming support (lower latency)
- Requires Riva server endpoint
- Experimental status

**Note**: Not recommended for general use yet. Use Whisper Turbo for production.

## Audio Processing

### Decoder

Uses **ffmpeg** for universal audio format support:
- MP3, WAV, AAC, FLAC, OGG, etc.
- Automatic format detection
- Resampling to 16kHz mono
- Conversion to float32 PCM

### VAD (Voice Activity Detection)

Uses **Silero VAD** for speech detection:
- Identifies speech vs. silence
- Trims non-speech segments
- Reduces processing time by ~30-50% on typical recordings
- Improves accuracy by focusing on speech

### Normalization

Audio is normalized for consistent processing:
- Sample rate: 16kHz (required by Whisper)
- Channels: Mono (stereo mixed down)
- Format: float32 PCM
- Range: [-1.0, 1.0]

## Configuration System

### Config Files

**Location**: `~/.config/vociferous/config.toml`

**Priority** (highest to lowest):
1. CLI flags (e.g., `--engine whisper_turbo`)
2. Environment variables (e.g., `VOCIFEROUS_ENGINE`)
3. Config file settings
4. Built-in defaults

**Key Settings**:
```toml
engine = "whisper_turbo"
device = "cpu"  # or "cuda"
model_cache_dir = "~/.cache/vociferous/models"

[params]
language = "en"
preset = "balanced"
enable_vad = true
clean_disfluencies = true
```

### Model Caching

Models are automatically downloaded and cached on first use:
- **Location**: `~/.cache/vociferous/models`
- **Whisper models**: Downloaded from HuggingFace (CTranslate2 format)
- **Voxtral models**: Downloaded from HuggingFace (Transformers format)
- **Silero VAD**: Bundled with package

## State Management

### Transcription Session

The `TranscriptionSession` class manages stateful transcription:

```python
# Push-based streaming API
session.start(language="en")
session.push_audio(chunk1)
session.push_audio(chunk2)
session.flush()
segments = session.poll_segments()
```

**Benefits**:
- Low memory footprint (chunks processed incrementally)
- Early output (segments available before full audio processed)
- Cancellable (can stop mid-transcription)

### History

Transcription history stored in JSONL format:
- **Location**: `~/.cache/vociferous/history/history.jsonl`
- Each line is a JSON object with metadata and transcript
- Configurable retention (default: 100 most recent)

## Error Handling

Vociferous uses typed errors and graceful degradation:

### Error Types
- `AudioDecodingError`: Invalid or unsupported audio format
- `ModelLoadError`: Engine initialization failed
- `TranscriptionError`: Transcription failed
- `ConfigError`: Invalid configuration

### Fallback Strategy
1. Try primary engine
2. If fails, log error and provide clear message
3. Suggest fixes (e.g., "Install ffmpeg for audio decoding")
4. Never crash silently—always inform user

## Performance Characteristics

### Typical Performance (RTF = Real-Time Factor)

**CPU (Intel i7)**:
- Fast preset: RTF ~0.3 (30s audio → 10s processing)
- Balanced preset: RTF ~0.5 (30s audio → 15s processing)
- High-accuracy preset: RTF ~1.5 (30s audio → 45s processing)

**GPU (NVIDIA RTX 3060)**:
- Fast preset: RTF ~0.1 (30s audio → 3s processing)
- Balanced preset: RTF ~0.15 (30s audio → 4.5s processing)
- High-accuracy preset: RTF ~0.4 (30s audio → 12s processing)

*RTF = Processing time / Audio duration. Lower is faster.*

### Memory Usage

- **Whisper Turbo**: ~2-4 GB RAM (int8 CPU), ~6-8 GB VRAM (float16 GPU)
- **Voxtral**: ~6-12 GB RAM/VRAM (depends on context length)
- **VAD**: ~200 MB RAM

### Disk Usage

- **Whisper large-v3-turbo**: ~1.5 GB
- **Whisper large-v3**: ~3 GB
- **Voxtral**: ~14 GB
- **Silero VAD**: ~50 MB

## Development Architecture

### Module Catalog

| Module | Responsibilities | Dependencies |
|--------|-----------------|--------------|
| `domain` | Core types, protocols | stdlib only |
| `engines` | ASR engine adapters | domain, engine runtimes |
| `audio` | Audio I/O, VAD | domain, ffmpeg, sounddevice |
| `storage` | Config, history, file I/O | domain, filesystem APIs |
| `app` | Use cases, session orchestration | domain, engines, audio, storage |
| `cli` | CLI commands, output sinks | app, config |
| `gui` | KivyMD graphical interface | app, config |

### Dependency Rules

- **Domain** has no dependencies (pure Python, stdlib only)
- **Adapters** depend only on domain + their specific runtime
- **Application** depends on domain + adapters (via protocols)
- **UI** depends on application + config

**Forbidden**:
- UI importing domain/adapters directly
- Adapters importing other adapters
- Circular dependencies between any modules

## Next Steps

- **[Getting Started](Getting-Started.md)**: Install and use Vociferous
- **[Engines & Presets](Engines-and-Presets.md)**: Choose the right engine and quality settings
- **[Development](Development.md)**: Contribute to the project
