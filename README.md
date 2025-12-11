# Vociferous

Local-first ASR with Canary-Qwen dual-pass as the primary engine, plus legacy Whisper Turbo and Voxtral options for compatibility. See `Planning and Documentation` for architecture and requirements.

## Requirements
- Python 3.11+
- `ffmpeg` available on PATH for decode.
- `sounddevice`/PortAudio for microphone capture (installed with the base package; ensure OS-specific PortAudio libs are available).
- GPU optional; CPU runs are supported. Models cache to `~/.cache/vociferous/models` automatically.

## Installation
- Base install (includes faster-whisper and Silero VAD): `pip install -e .` or `pip install -r requirements.txt`
- Optional extras:
    - `pip install -e .[polish]` for grammar/fluency polishing (llama.cpp + HF hub download)
    - `pip install -e .[gui]` for the Vociferous GUI (KivyMD-based graphical interface)
    - `pip install -e .[voxtral]` for Voxtral local transformer support (transformers + torch)
    - `pip install -e .[dev]` for tests, typing, and linting tools

**Maintenance:** When changing runtime dependencies in `pyproject.toml`, update `requirements.txt` to match so both install paths stay in sync.

## Engines and Presets

### Engines

All engines use a simple batch interface - complete audio file in, complete transcript out.

- **`canary_qwen`** (default): Dual-pass (ASR + optional refinement) using Canary-Qwen 2.5B. Defaults to a mock, dependency-light mode; set `use_mock=false` and install `transformers` + `torch` to run the real model. See `docs/engines/canary_qwen.md` for details.
- **`whisper_turbo`** (legacy): Batch processing via CTranslate2. Fast and offline; kept for compatibility and quick drafts.
- **`voxtral_local`** (legacy): Batch processing via transformers. Mistral-based with smart punctuation and grammar; slower, legacy option.
- **`parakeet_rnnt`**: NVIDIA Parakeet RNNT via Riva endpoint (optional, experimental). Note: This engine uses a different architecture for real-time applications.

### Engine Interface

Engines use a simple batch interface:

```python
segments = engine.transcribe_file(audio_path)
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

### Quality Presets (`whisper_turbo` engine - legacy)
Control the speed/quality tradeoff with `-p/--preset`:

**`balanced`** (default)
- **Model**: `openai/whisper-large-v3-turbo` (optimized variant)
- **Compute**: `float16` on GPU, `int8` on CPU
- **Beam size**: 1 (greedy decoding)
- **Batch size**: 12
- **Use case**: Best general-purpose option. Good accuracy with reasonable speed.

**`fast`**
- **Model**: `openai/whisper-large-v3-turbo`
- **Compute**: `int8_float16` mixed precision (speed optimized)
- **Beam size**: 1 (greedy decoding)
- **Batch size**: 16 (larger batches for throughput)
- **Use case**: Maximum speed for quick drafts or when processing many files. Slightly lower accuracy.

**`high_accuracy`**
- **Model**: `openai/whisper-large-v3` (full model, not turbo)
- **Compute**: `float16` on GPU, `int8` on CPU
- **Beam size**: 2 (beam search explores multiple hypotheses)
- **Batch size**: 8 (smaller batches, more careful processing)
- **Use case**: Best quality for important transcriptions. Significantly slower but more accurate, especially with difficult audio.

**Examples**:
```bash
# Default balanced preset
vociferous transcribe meeting.wav

# Fast preset for quick turnaround
vociferous transcribe podcast.mp3 --preset fast

# High accuracy for important content
vociferous transcribe interview.wav -p high_accuracy -o transcript.txt
```

**Note**: For fine-grained control beyond presets, edit `~/.config/vociferous/config.toml` to set specific model names, compute types, beam sizes, and batch parameters.

## Key behaviors
- `vociferous transcribe` defaults to `canary_qwen` (mock by default; set `use_mock=false` for the full model). Legacy engines emit a deprecation warning.
- Disfluency cleaning is on by default for Whisper; toggle with `--no-clean-disfluencies`.
- Default device/compute/model pull from config; device defaults to CPU unless overridden.

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
Displays: All user commands PLUS `decode`, `vad`, `condense`, `record`, `transcribe` (workflow orchestration), and `refine` (planned text-only refinement) for manual pipeline construction.

Example (truncated):
```bash
$ vociferous --dev-help
Usage: vociferous [OPTIONS] COMMAND

Audio Components:
	decode     Normalize audio to PCM mono 16kHz
	vad        Detect speech boundaries
	condense   Remove silence using VAD timestamps
	record     Capture microphone audio

Workflow Commands:
	transcribe Main transcription workflow (decode → VAD → condense → Canary ASR → Canary Refiner)
	refine     Text-only refinement (planned; Canary LLM mode)
```

**When to use each:**
- New user? Start with `vociferous --help` to see the essentials.
- Need to debug or understand internals? Use `vociferous --dev-help` to see all components.
- Building custom pipelines? Use `--dev-help` to access low-level tools.

### Main Commands

- `vociferous transcribe <file>` - Transcribe audio file to stdout. Common flags: `-e`/`--engine`, `-l`/`--language`, `-o`/`--output`, `-p`/`--preset`.
  - Example: `vociferous transcribe recording.wav -e voxtral_local -o transcript.txt`
- `vociferous languages` - List all supported language codes (ISO 639-1) for Whisper and Voxtral engines.
- `vociferous check` - Verify local prerequisites (ffmpeg, sounddevice).
- `vociferous-gui` - Launch the graphical user interface (requires `[gui]` extra).

### Developer Commands (accessible via `--dev-help`)

For manual pipeline debugging and component-level control:
- `vociferous decode <file>` - Normalize audio to PCM mono 16kHz
- `vociferous vad <wav>` - Detect speech boundaries and output timestamps
- `vociferous condense <timestamps> <wav>` - Remove silence using VAD timestamps
- `vociferous record` - Capture microphone audio
- `vociferous transcribe <file>` - Workflow orchestrator (decode → VAD → condense → Canary ASR → Canary Refiner)
- `vociferous refine <transcript>` - Text-only refinement (planned developer component)

**Note:** Most users should use `transcribe` instead of manual component chaining. Developer commands are for debugging and understanding the internals.

### Command Options

- `-e|--engine canary_qwen|whisper_turbo|voxtral_local` - Select engine (Canary-Qwen default; Whisper/Voxtral are legacy options).
- `-p|--preset high_accuracy|balanced|fast`; `--fast` shortcut for `preset=fast`.
- `-l|--language <code>` - Language code (e.g., `en`, `es`, `fr`) or `auto` for detection. See `vociferous languages` for full list.
- Whisper controls: `--enable-batching/--batch-size`, `--beam-size`, `--vad-filter/--no-vad-filter`, `--word-timestamps`, `--whisper-temperature`.
- Voxtral controls: `--prompt`, `--max-new-tokens`, `--gen-temperature`.
- Output/UX: `--output <path>`, `--clipboard`, `--save-history`.

## Development
- Run tests: `pytest` (strict type hints enforced).
- Code style: frozen dataclasses in domain; adapters avoid importing UI/app layers (ports-and-adapters).
