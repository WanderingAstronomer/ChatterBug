# Canary-Qwen 2.5B (ASR + LLM)

Hybrid encoder/decoder model that can both transcribe audio and refine text.

## Modes
- **ASR (default)**: audio → raw transcript (`params.mode = "asr"`).
- **LLM**: text refinement (`params.mode = "llm"`, call `set_text_input` then `flush`).
- **Dual-pass**: run ASR then call `refine_text` on the raw output.

## Requirements (real model)
- `transformers` and `torch` installed.
- Model id: `nvidia/canary-qwen-2.5b`.
- Set `params.use_mock = "false"` to load the real model.

> Note: With `use_mock=true` (default), no model download occurs; outputs are deterministic placeholders for offline testing.

## Quickstart (mock/offline)
```bash
vociferous transcribe-canary input.wav --mock
```

## Quickstart (real model)
```bash
pip install transformers torch
vociferous transcribe-canary input.wav --no-mock
```

## Parameters
- `mode`: `"asr"` or `"llm"` (defaults to `"asr"`).
- `use_mock`: `"true"`/`"false"`; keep `"true"` for lightweight testing.
- `device` / `compute_type`: forwarded from `EngineConfig` (defaults follow app config).

## CLI examples
- ASR + refine (mock):
  ```bash
  vociferous transcribe-canary sample.wav --mock --refine
  ```
- ASR only (real model):
  ```bash
  vociferous transcribe-canary sample.wav --no-mock --no-refine
  ```
