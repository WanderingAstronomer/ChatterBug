# Polisher Performance & Behavior Report (2025-12-05)

## Context
- Engines: Whisper Turbo (faster-whisper), Voxtral, Parakeet RNNT.
- Polisher: Qwen2.5-1.5B-Instruct `q4_k_m` GGUF via llama.cpp; auto-download through `huggingface_hub`.
- GPU: CUDA enabled; polisher offloads layers (`gpu_layers=99` when CUDA detected).
- Input: `samples/Recording 2.flac` (~30s). Command baseline used `--clean-disfluencies`.
- Env: default threads unless overridden; `NUMEXPR_MAX_THREADS` can be set via config/CLI.

## Timing Results (single run, wall clock)
| Engine | No polish | With polish | Overhead |
| --- | --- | --- | --- |
| Whisper Turbo | 3.32s | 5.20s | +1.88s |
| Voxtral | 7.23s | 8.87s | +1.64s |
| Parakeet RNNT | 13.58s | 15.39s | +1.81s |

Runtime-to-duration ratios (GPU run time ÷ 34.37s audio):
- Whisper Turbo: 0.10× (no polish), 0.15× (polish)
- Voxtral: 0.21× (no polish), 0.26× (polish)
- Parakeet RNNT: 0.40× (no polish), 0.45× (polish)

### CPU-only rerun (CUDA disabled, single run)
- Env: `CUDA_VISIBLE_DEVICES=""`, `NUMEXPR_MAX_THREADS=8`, CLI `--device cpu`, `--compute-type int8` for Whisper/Voxtral, `--compute-type float32` for Parakeet, `--polish-gpu-layers 0` when polishing.
- Input: `samples/Recording 2.flac` (ffmpeg measured ~34.37s). Output suppressed for timing.

| Engine | No polish | With polish | Overhead |
| --- | --- | --- | --- |
| Whisper Turbo | 11.01s | 12.05s | +1.04s |
| Voxtral | 107.07s | 108.79s | +1.72s |
| Parakeet RNNT | 20.66s | 21.89s | +1.23s |

Runtime-to-duration ratios (run time ÷ 34.37s audio):
- Whisper Turbo: 0.32× (no polish), 0.35× (polish)
- Voxtral: 3.12× (no polish), 3.17× (polish)
- Parakeet RNNT: 0.60× (no polish), 0.64× (polish)

Notes:
- Overhead is primarily the polisher generation; models stayed on GPU.
- For more stable numbers, run each command 3–5x and average.

## Output Quality
- Whisper: Polisher fixed mid-word splits and punctuation without adding explanations after prompt tightening.
- Voxtral: Output already strong; polisher maintained punctuation and casing.
- Parakeet: Polisher added capitalization/punctuation to otherwise bare text.

## Logging/Noise Mitigation
- NeMo logs reduced to ERROR level; one deprecation warning may still show.
- `llama_context` and `NumExpr` notices are informational; set `NUMEXPR_MAX_THREADS` if desired.

## How to Reproduce (timing)

GPU (default CUDA, polished/unpolished):
```bash
/usr/bin/time -f "whisper_gpu_no_polish wall=%e sec" \
  ./.venv/bin/python -m chatterbug.cli.main transcribe "samples/Recording 2.flac" \
  --engine whisper_turbo --clean-disfluencies --no-polish >/dev/null

/usr/bin/time -f "whisper_gpu_polish wall=%e sec" \
  ./.venv/bin/python -m chatterbug.cli.main transcribe "samples/Recording 2.flac" \
  --engine whisper_turbo --clean-disfluencies --polish \
  --polish-gpu-layers 99 >/dev/null
```

CPU-only (CUDA disabled, polished/unpolished):
```bash
CUDA_VISIBLE_DEVICES="" NUMEXPR_MAX_THREADS=8 \
/usr/bin/time -f "whisper_cpu_no_polish wall=%e sec" \
  ./.venv/bin/python -m chatterbug.cli.main transcribe "samples/Recording 2.flac" \
  --engine whisper_turbo --device cpu --compute-type int8 \
  --clean-disfluencies --no-polish --vad-filter --chunk-ms 30000 --trim-tail-ms 800 >/dev/null

CUDA_VISIBLE_DEVICES="" NUMEXPR_MAX_THREADS=8 \
/usr/bin/time -f "whisper_cpu_polish wall=%e sec" \
  ./.venv/bin/python -m chatterbug.cli.main transcribe "samples/Recording 2.flac" \
  --engine whisper_turbo --device cpu --compute-type int8 \
  --clean-disfluencies --polish --polish-gpu-layers 0 \
  --vad-filter --chunk-ms 30000 --trim-tail-ms 800 >/dev/null
```

Repeat for `voxtral` and `parakeet_rnnt` with/without `--polish`, adjusting `--compute-type` to `float32` for Parakeet RNNT on CPU and keeping `--polish-gpu-layers 0` when polishing on CPU.

## Open Follow-ups
- Optional: average multiple runs and log in CI.
- Optional: add a `--quiet` flag to further reduce third-party warnings.
- Optional: add a prefetch helper to download the GGUF polisher model ahead of first use.
