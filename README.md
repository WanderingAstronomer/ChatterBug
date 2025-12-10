# Vociferous

Local-first ASR with faster-whisper (CTranslate2) as the default engine and an offline Voxtral transformer option for smarter punctuation. See `Planning and Documentation` for architecture and requirements.

## Requirements
- Python 3.11+
- `ffmpeg` available on PATH for decode.
- `sounddevice`/PortAudio for microphone capture (installed with the base package; ensure OS-specific PortAudio libs are available).
- GPU optional; CPU runs are supported. Models cache to `~/.cache/vociferous/models` automatically.

## Installation
- Base install (includes faster-whisper and Silero VAD): `pip install -e .`
- Optional extras:
	- `pip install -e .[polish]` for grammar/fluency polishing (llama.cpp + HF hub download)
	- `pip install -e .[gui]` for the Vociferous GUI (KivyMD-based graphical interface)
	- `pip install -e .[voxtral]` for Voxtral local transformer support (transformers + torch)
	- `pip install -e .[dev]` for tests, typing, and linting tools

## Engines and Presets

### Engines
- **`whisper_turbo`** (default): CTranslate2-based faster-whisper engine. Fast, accurate, runs offline. Best for general use.
- **`voxtral_local`**: Mistral-based transformer with smart punctuation and grammar. Requires `[voxtral]` extra. Slower but produces more natural text.
- **`canary_qwen`**: Dual-pass (ASR + optional refinement) using Canary-Qwen 2.5B. Defaults to a mock, dependency-light mode; set `use_mock=false` and install `transformers` + `torch` to run the real model. See `docs/engines/canary_qwen.md` for details.
- **`parakeet_rnnt`**: NVIDIA Parakeet RNNT via Riva endpoint (optional). Experimental streaming support.

Engines are stateful and push-based: `start()` → `push_audio()` → `flush()` → `poll_segments()`; the CLI orchestrates via `TranscriptionSession`.

### Quality Presets (`whisper_turbo` engine)
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
- `vociferous transcribe` defaults to `whisper_turbo` (local faster-whisper) for offline/low-dependency use.
- Disfluency cleaning is on by default for Whisper; toggle with `--no-clean-disfluencies`.
- Default device/compute/model pull from config; device defaults to CPU unless overridden.

## Configuration
- Config file: `~/.config/vociferous/config.toml` (created on first run). CLI flags override config values.
- Key fields: `engine` (default `whisper_turbo`), `model_cache_dir`, `device`, `compute_type`, `params`.
- Model cache: `~/.cache/vociferous/models` (auto-created).
- History: JSONL-backed history stored under `~/.cache/vociferous/history/history.jsonl`.

## CLI Usage
- `vociferous transcribe <file>` - Transcribe audio file to stdout. Common flags: `-e`/`--engine`, `-l`/`--language`, `-o`/`--output`, `-p`/`--preset`.
  - Example: `vociferous transcribe recording.wav -e voxtral_local -o transcript.txt`
- `vociferous languages` - List all supported language codes (ISO 639-1) for Whisper and Voxtral engines.
- `vociferous check` - Verify local prerequisites (ffmpeg, sounddevice).
- `vociferous-gui` - Launch the graphical user interface (requires `[gui]` extra).
- `-e|--engine whisper_turbo|voxtral_local` - Select engine.
- `-p|--preset high_accuracy|balanced|fast`; `--fast` shortcut for `preset=fast`.
- `-l|--language <code>` - Language code (e.g., `en`, `es`, `fr`) or `auto` for detection. See `vociferous languages` for full list.
- Whisper controls: `--enable-batching/--batch-size`, `--beam-size`, `--vad-filter/--no-vad-filter`, `--word-timestamps`, `--whisper-temperature`.
- Voxtral controls: `--prompt`, `--max-new-tokens`, `--gen-temperature`.
- Polisher: `--polish/--no-polish`, `--polish-model`, `--polish-max-tokens`, `--polish-temperature`, `--polish-gpu-layers`, `--polish-context-length`.
- Output/UX: `--output <path>`, `--clipboard`, `--save-history`.

## Development
- Run tests: `pytest` (strict type hints enforced).
- Code style: frozen dataclasses in domain; adapters avoid importing UI/app layers (ports-and-adapters).
