# Vociferous

Local-first ASR with Canary-Qwen dual-pass as the primary engine, plus Whisper Turbo as a fallback option. See `docs/ARCHITECTURE.md` for detailed architecture and requirements.

## Requirements
- Python 3.11+
- `ffmpeg` available on PATH for decode.
- `sounddevice`/PortAudio for microphone capture (installed with the base package; ensure OS-specific PortAudio libs are available).
- **NVIDIA GPU with CUDA required for Canary-Qwen** (default engine). Whisper Turbo works on CPU.
- Models cache to `~/.cache/vociferous/models` automatically.

## Installation
- Base install: `pip install -e .`
  - Includes: NeMo toolkit, torch>=2.6.0, faster-whisper, Silero VAD, and all required dependencies
- Optional extras:
    - `pip install -e .[gui]` for the Vociferous GUI (KivyMD-based graphical interface)
    - `pip install -e .[dev]` for tests, typing, and linting tools

All dependencies are managed in `pyproject.toml` as the single source of truth.

## Engines

All engines use a simple batch interface - complete audio file in, complete transcript out.

- **`canary_qwen`** (default): Dual-pass (ASR + refinement) using Canary-Qwen 2.5B via NeMo. **Requires CUDA GPU** with ~6GB free VRAM. Produces high-quality transcripts with grammar and punctuation refinement.
- **`whisper_turbo`** (fallback): Batch processing via CTranslate2/faster-whisper. Works on CPU and GPU. Fast and offline; use when GPU is unavailable or for quick drafts.

### Engine Interface

Engines use a simple batch interface:

```python
segments = engine.transcribe_file(audio_path, options)
```

The engine receives a preprocessed audio file (decoded, VAD-filtered, silence removed) and returns the complete transcript in one operation.

### Audio Pipeline

Before transcription, audio is preprocessed in stages:

1. **Decode:** Normalize to PCM mono 16kHz
2. **VAD:** Detect speech boundaries
3. **Condense:** Remove silence
4. **Transcribe:** Engine receives clean, condensed audio

Each stage is batch processing - complete file in, complete file out.

### Why Batch Processing?

- User submits complete audio files (not live streams)
- ML models work best on complete audio
- Simpler architecture (no state management)
- Easier to test and debug

## Key behaviors
- `vociferous transcribe` defaults to `canary_qwen` (requires CUDA GPU). Use `--engine whisper_turbo` for CPU fallback.
- Canary-Qwen includes automatic refinement (grammar, punctuation) in a second pass using the same model.
- Disfluency cleaning is on by default for Whisper; toggle with `--no-clean-disfluencies`.
- Default device is `cuda` for Canary-Qwen, `auto` for Whisper Turbo.

## Performance: Warm Model Daemon

For best performance when transcribing multiple files, start the warm model daemon:

```bash
# Start daemon (loads model into GPU memory)
vociferous daemon start

# Now transcriptions are instant (~2-5s instead of ~29s)
vociferous transcribe audio1.wav --use-daemon
vociferous transcribe audio2.wav --use-daemon

# Stop daemon when done
vociferous daemon stop
```

**Performance comparison:**

| Method | First File | Subsequent Files |
|--------|-----------|------------------|
| Direct (cold start) | ~29s | ~29s each |
| Daemon (warm model) | ~29s | **~2-5s each** |

The daemon is **automatically used** when the GUI is running.

**Commands:**
- `vociferous daemon start` - Start daemon (model loads in ~16s)
- `vociferous daemon stop` - Stop daemon
- `vociferous daemon status` - Check if running
- `vociferous daemon logs` - View daemon logs
- `vociferous daemon restart` - Restart daemon

See [Daemon Documentation](docs/daemon.md) for details.

## Configuration
- Config file: `~/.config/vociferous/config.toml` (created on first run). CLI flags override config values.
- Key fields: `engine` (default `canary_qwen`), `model_name` (default `nvidia/canary-qwen-2.5b`), `model_cache_dir`, `device`, `compute_type`, `params`.
- Model cache: `~/.cache/vociferous/models` (auto-created).
- History: JSONL-backed history stored under `~/.cache/vociferous/history/history.jsonl`.

## CLI Usage

### Getting Help

Vociferous provides two help modes to serve different audiences:

**User Help (`--help`)** - Shows essential commands for everyday transcription:
```bash
vociferous --help
```
Displays: `transcribe`, `languages`, `check` — everything most users need.

Example (truncated):
```bash
$ vociferous --help
Usage: vociferous [OPTIONS] COMMAND

Commands:
	transcribe  Transcribe audio file to text
	languages   List supported language codes
	check       Verify system prerequisites
```

**Developer Help (`--dev-help`)** - Shows all commands including low-level debugging tools:
```bash
vociferous --dev-help
```
Displays: All user commands PLUS `decode`, `vad`, `condense`, `record`, `transcribe` (workflow orchestration), and `refine` (text-only refinement) for manual pipeline construction.

Example (truncated):
```bash
$ vociferous --dev-help
Usage: vociferous [OPTIONS] COMMAND

Audio Components:
	decode     Normalize audio to PCM mono 16kHz
	vad        Detect speech boundaries
	condense   Remove silence using VAD timestamps
	record     Capture microphone audio

Refinement Components:
	refine     Text-only refinement (Canary LLM mode)

Workflow Commands:
	transcribe Main transcription workflow (decode → VAD → condense → Canary ASR → Canary Refiner)
```

**When to use each:**
- New user? Start with `vociferous --help` to see the essentials.
- Need to debug or understand internals? Use `vociferous --dev-help` to see all components.
- Building custom pipelines? Use `--dev-help` to access low-level tools.

### Main Commands

- `vociferous transcribe <file>` - Transcribe audio file to stdout. Common flags: `-e`/`--engine`, `-l`/`--language`, `-o`/`--output`, `--refine`/`--no-refine`.
  - Example: `vociferous transcribe recording.wav -o transcript.txt`
  - Example (CPU): `vociferous transcribe recording.wav -e whisper_turbo`
- `vociferous languages` - List all supported language codes (ISO 639-1).
- `vociferous check` - Verify local prerequisites (ffmpeg, sounddevice).
- `vociferous-gui` - Launch the graphical user interface (requires `[gui]` extra).

### Developer Commands (accessible via `--dev-help`)

For manual pipeline debugging and component-level control:
- `vociferous decode <file>` - Normalize audio to PCM mono 16kHz
- `vociferous vad <wav>` - Detect speech boundaries and output timestamps
- `vociferous condense <timestamps> <wav>` - Remove silence using VAD timestamps
- `vociferous record` - Capture microphone audio
- `vociferous refine <transcript>` - Text-only refinement via Canary LLM

**Note:** Most users should use `transcribe` instead of manual component chaining. Developer commands are for debugging and understanding the internals.

### Command Options

- `-e|--engine canary_qwen|whisper_turbo` - Select engine (Canary-Qwen default, requires GPU; Whisper Turbo for CPU).
- `--refine/--no-refine` - Toggle second-pass refinement (Canary-Qwen only).
- `-l|--language <code>` - Language code (e.g., `en`, `es`, `fr`) or `auto` for detection. See `vociferous languages` for full list.
- Whisper controls: `--beam-size`, `--vad-filter/--no-vad-filter`, `--word-timestamps`.
- Output/UX: `--output <path>`, `--clipboard`, `--save-history`.

## Development
- Run tests: `pytest` (64 tests, all using real files - no mocks).
- Full test suite takes ~4 minutes with CUDA GPU.
- Code style: frozen dataclasses in domain; adapters avoid importing UI/app layers (ports-and-adapters).
- Type checking: `mypy --strict` on all modules.
