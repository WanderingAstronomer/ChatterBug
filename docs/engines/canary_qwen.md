# Canary-Qwen Engine (ASR + LLM)

Hybrid encoder/decoder model that can both transcribe audio and refine text using dual-pass architecture.

## Modes
- **ASR (default)**: audio → raw transcript (`params.mode = "asr"`).
- **LLM**: text refinement (`params.mode = "llm"`, call `set_text_input` then `flush`).
- **Dual-pass**: run ASR then call `refine_text` on the raw output for refined transcripts.

## Requirements

**Python Packages:**
- `transformers>=4.38.0`
- `torch>=2.0.0`
- `accelerate>=0.28.0`

**Model:**
- Model repository: `nvidia/canary-qwen-2.5b`
- Cache location: `~/.cache/vociferous/models/` (configurable)
- Downloaded automatically on first use if not cached

**Check Dependencies:**
```bash
vociferous deps check --engine canary_qwen
```

## Installation

**1. Install required packages:**
```bash
pip install transformers torch accelerate
```

**2. Verify installation:**
```bash
vociferous deps check --engine canary_qwen
# Should show: ✓ All dependencies satisfied
```

**3. First run (downloads model):**
```bash
vociferous transcribe audio.wav --engine canary_qwen
# Model downloads to cache on first use
```

## Usage

**Basic transcription (ASR only):**
```bash
vociferous transcribe audio.wav --engine canary_qwen --no-refine
```

**Transcription with refinement (dual-pass):**
```bash
vociferous transcribe audio.wav --engine canary_qwen --refine
```

**Custom refinement instructions:**
```bash
vociferous transcribe audio.wav --engine canary_qwen --refine \
  --refinement-instructions "Medical terminology, formal tone"
```

## Parameters
- `mode`: `"asr"` or `"llm"` (defaults to `"asr"`).
- `device`: GPU/CPU selection (defaults from `config.toml`).
- `compute_type`: Precision settings (defaults from `config.toml`).

## Fail-Loud Behavior

**Missing Dependencies:**
If required packages are not installed, the engine fails immediately with clear error messages:

```bash
$ vociferous transcribe audio.wav --engine canary_qwen

❌ Error: Missing required packages for canary_qwen engine
   - transformers>=4.38.0 (not installed)
   - torch>=2.0.0 (not installed)

Run: vociferous deps check --engine canary_qwen
Then: pip install transformers torch accelerate
```

**No Implicit Installs:**
- The system never automatically installs packages
- The system never silently falls back to mock implementations
- All dependency issues are explicit and actionable

## Performance Notes

- Model stays loaded between ASR and refinement passes (no reload overhead)
- Single model in memory for both passes (efficient VRAM/RAM usage)
- Dual-pass typically 1.5-2x slower than ASR-only, but produces significantly better quality
