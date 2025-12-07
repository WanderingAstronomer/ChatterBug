# Vociferous

Local-first ASR with faster-whisper (CTranslate2) as the default engine and optional vLLM-backed Whisper/Voxtral engines for remote acceleration. See `Planning and Documentation` for architecture and requirements.

## Requirements
- Python 3.11+
- `ffmpeg` available on PATH for decode.
- vLLM server reachable at `http://localhost:8000` for `whisper_vllm` / `voxtral_vllm` (optional). Use `vociferous serve-vllm --model <model>` for a quick local server, or point `--vllm-endpoint` to an existing one.
- `sounddevice`/PortAudio for microphone capture (installed with the base package; ensure OS-specific PortAudio libs are available).
- GPU optional; CPU runs are supported but vLLM benefits from GPU for throughput. Models cache to `~/.cache/vociferous/models` automatically.

## Installation
- Base install (includes OpenAI client, faster-whisper, transformers): `pip install -e .`
- Optional extras:
	- `pip install -e .[polish]` for grammar/fluency polishing (llama.cpp + HF hub download)
	- `pip install -e .[gui]` for the Luciferous GUI (KivyMD-based graphical interface)
	- `pip install -e .[dev]` for tests, typing, and linting tools

## Engines and presets
- Engines: `whisper_turbo` (default, CTranslate2 local), `voxtral_local` (transformers local), `whisper_vllm` (remote), `voxtral_vllm` (remote).
- Presets: `high_accuracy` (whisper-large-v3, beam=2), `balanced` (default for vLLM; whisper-large-v3-turbo), `fast` (turbo tuned for speed). `--fast` aliases `preset=fast`.
- Engines are stateful and push-based: `start()` → `push_audio()` → `flush()` → `poll_segments()`; the CLI orchestrates via `TranscriptionSession`.

## Key behaviors
- `vociferous transcribe` defaults to `whisper_turbo` (local faster-whisper) for offline/low-dependency use.
- Disfluency cleaning is on by default for Whisper; toggle with `--no-clean-disfluencies`.
- Default device/compute/model pull from config; device defaults to CPU unless overridden.

## Configuration
- Config file: `~/.config/vociferous/config.toml` (created on first run). CLI flags override config values.
- Key fields: `engine` (default `whisper_turbo`), `vllm_endpoint` (default `http://localhost:8000`), `model_cache_dir`, `device`, `compute_type`, `params`.
- Model cache: `~/.cache/vociferous/models` (auto-created).
- History: JSONL-backed history stored under `~/.cache/vociferous/history/history.jsonl`.

## CLI Usage
- `vociferous transcribe <file>` - Transcribe audio file to stdout.
- `luciferous` - Launch the graphical user interface (requires `[gui]` extra).
- `--engine whisper_vllm|voxtral_vllm|whisper_turbo|voxtral_local` - Select engine.
- `--preset high_accuracy|balanced|fast` (balanced default for vLLM engines); `--fast` shortcut for `preset=fast`.
- `--vllm-endpoint http://host:port` - Target vLLM server for vLLM engines.
- Whisper controls: `--enable-batching/--batch-size`, `--beam-size`, `--vad-filter/--no-vad-filter`, `--word-timestamps`, `--whisper-temperature`.
- Voxtral controls: `--prompt`, `--max-new-tokens`, `--gen-temperature`.
- Polisher: `--polish/--no-polish`, `--polish-model`, `--polish-max-tokens`, `--polish-temperature`, `--polish-gpu-layers`, `--polish-context-length`.
- Output/UX: `--output <path>`, `--clipboard`, `--save-history`.
- `vociferous check` - Verify local prerequisites (ffmpeg, sounddevice).
- `vociferous check-vllm` - Validate connectivity and list models served by a vLLM endpoint.
- `vociferous serve-vllm --model <name>` - Convenience wrapper to launch `vllm serve` with sane defaults (use your own process manager for production).

## Development
- Run tests: `pytest` (strict type hints enforced).
- Code style: frozen dataclasses in domain; adapters avoid importing UI/app layers (ports-and-adapters).
