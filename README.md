# ChatterBug

Local-first ASR with pluggable engines (Whisper Turbo default, Voxtral smart mode optional, Parakeet RNNT running locally via NeMo). See `Planning and Documentation` for architecture and requirements.

## Requirements for all-local runs
- Python 3.11+
- `ffmpeg` available on PATH (for decode)
- `sounddevice`/PortAudio for microphone capture (installed with the base package; ensure OS-specific PortAudio libs are available)
- GPU optional; CPU supported with int8 defaults.
- Engine dependencies (faster-whisper, transformers, NeMo RNNT, silero VAD) install with the base package; models download on first use to `~/.cache/chatterbug/models`.

## Installation
- Base install with bundled engine deps: `pip install -e .`
- Optional extras:
	- `pip install -e .[polish]` for grammar/fluency polishing (llama.cpp + HF hub download)
	- `pip install -e .[hotkeys]` for hotkey listener (keyboard)
	- `pip install -e .[gui]` for future desktop GUI shell (PySide6)
	- `pip install -e .[dev]` for tests, typing, and linting tools

## Key behaviors
- Engines are stateful and push-based: `start()` → `push_audio()` → `flush()` → `poll_segments()`; the CLI/TUI/GUI orchestrate this via `TranscriptionSession`.
- Whisper Turbo defaults to VAD-trimmed sliding windows with batched inference enabled for file transcription (`batch_size=16`). Batching provides 2-4x speedup for non-realtime processing.
- Default model is `distil-whisper/distil-large-v3` for English (5x faster than large-v3-turbo with similar accuracy).
- Disfluency cleaning is enabled by default (removes stutters, repeated words, stray hyphens). Use `--no-clean-disfluencies` to disable.
- Default model/device/precision come from config; the device defaults to CPU unless explicitly set to `cuda` via config or CLI. CUDA uses float16 even when int8 is requested for stability.

## Configuration
- Config file: `~/.config/chatterbug/config.toml` (created on first run). CLI flags override config values.
- Model cache: `~/.cache/chatterbug/models` (auto-created). Models load from local cache by default.
- History: JSONL-backed history stored under `~/.cache/chatterbug/history/history.jsonl`; serialization uses Pydantic `model_dump()` for stability.

## CLI Usage
- `chatterbug transcribe <file>` - Transcribe audio file to stdout
- `--output <path>` - Write transcript to file
- `--engine voxtral` or `--engine parakeet_rnnt` - Pick engine (Parakeet RNNT runs locally)
- `--fast` - Enable fast mode: batched inference, distil-large-v3 for English, beam_size=1, optimized settings (tradeoff: speed vs slight accuracy reduction)
- `--enable-batching --batch-size N` - Control batched Whisper Turbo (enabled by default for files with batch_size=16)
- `--vad-filter/--no-vad-filter` and `--word-timestamps` - Control VAD trimming and word timing
- `--no-clean-disfluencies` - Disable disfluency cleaning (enabled by default; removes stutters, repeated words, hyphens)
- `--polish/--no-polish` and `--polish-model <name>` - Optional transcript polisher (defaults to Qwen2.5-1.5B-Instruct q4_k_m GGUF)
- `--polish-max-tokens`, `--polish-temperature`, `--polish-gpu-layers`, `--polish-context-length` - Control llama.cpp polish generation
- `--beam-size`, `--whisper-temperature` - Whisper decode knobs; unset defers to library defaults
- `--prompt`, `--max-new-tokens`, `--gen-temperature` - Voxtral smart-mode knobs
- `chatterbug listen` - Live microphone transcription (experimental; batching disabled for low latency)
- `chatterbug check` - Verify prerequisites (ffmpeg, sounddevice)

## Development
- Run tests: `pytest` (162 tests, strict type hints enforced). Pull-based legacy tests removed; all engines use push-based streaming shims.
- Code style: frozen dataclasses in domain; adapters avoid importing UI/app layers (ports-and-adapters).

## GUI readiness
`chatterbug/gui` contains a placeholder shell; desktop UI will reuse the same core app services (CLI/TUI already in place).
