# Engines and Presets

Vociferous supports multiple transcription engines and quality presets. This page explains the differences, trade-offs, and when to use each.

## Available Engines

### 1. Whisper Turbo (Default)

**Technology**: OpenAI's Whisper large-v3-turbo via faster-whisper (CTranslate2 backend)

**Characteristics**:
- **Speed**: ~8x faster than standard Whisper large-v3
- **Accuracy**: High (optimized variant maintains quality)
- **CPU-Friendly**: int8 quantization for efficient CPU inference
- **GPU-Accelerated**: Automatic float16 on CUDA devices
- **Offline**: Fully local, no network required
- **Languages**: 99 languages supported

**Use Cases**:
- General-purpose transcription
- Fast turnaround needed
- CPU-only environments
- Batch processing
- Daily transcription tasks

**Installation**:
```bash
pip install -e .  # Included in base install
```

**Usage**:
```bash
vociferous transcribe file.wav --engine whisper_turbo
```

**Technical Details**:
- Model: OpenAI Whisper large-v3-turbo (CTranslate2 format)
- Size: ~1.5 GB
- Architecture: Encoder-decoder transformer
- Processing: 30-second sliding windows with 5s overlap
- VAD: Silero VAD for silence trimming

---

### 2. Voxtral Local

**Technology**: Mistral-based transformer with enhanced punctuation and grammar

**Characteristics**:
- **Punctuation**: Superior to Whisper for natural text
- **Grammar**: Better sentence structure and formatting
- **Context**: Long-context understanding (up to 128k tokens)
- **Speed**: Slower than Whisper (~3-5x processing time)
- **Quality**: More natural, publication-ready text
- **Offline**: Fully local, no network required

**Use Cases**:
- Publication-quality transcripts
- Long-form content (lectures, interviews)
- When punctuation and formatting matter
- Professional documentation
- Content where readability is critical

**Installation**:
```bash
pip install -e .[voxtral]
```

**Usage**:
```bash
vociferous transcribe lecture.mp3 --engine voxtral_local
```

**Technical Details**:
- Model: Mistral-based transformer (~14 GB)
- Architecture: Decoder-only transformer
- Context window: Up to 128k tokens
- Processing: Chunk-based with overlap

**Trade-offs**:
- ✅ Better punctuation and grammar
- ✅ More natural text output
- ✅ Long-context understanding
- ❌ Slower than Whisper
- ❌ Larger model size
- ❌ Higher GPU memory requirements

---

### 3. Parakeet RNNT (Experimental)

**Technology**: NVIDIA Parakeet RNNT via Riva endpoint

**Characteristics**:
- **Streaming**: Low-latency streaming support
- **Speed**: Fast inference on NVIDIA GPUs
- **Status**: Experimental, not production-ready
- **Requires**: Riva server endpoint

**Use Cases**:
- Real-time transcription (future)
- NVIDIA GPU deployment
- Streaming applications (experimental)

**Installation**:
```bash
# Requires separate Riva setup
# Not recommended for general use
```

**Note**: This engine is experimental. Use Whisper Turbo or Voxtral for production workloads.

---

## Quality Presets (Whisper Turbo)

Presets control the speed/quality trade-off for the Whisper Turbo engine.

### Preset Comparison Table

| Preset | Model | Compute Type | Beam Size | Batch Size | Speed | Accuracy | Best For |
|--------|-------|--------------|-----------|------------|-------|----------|----------|
| **fast** | turbo | int8_float16 | 1 | 16 | Fastest | Good | Quick drafts, batch jobs |
| **balanced** | turbo | auto | 1 | 12 | Fast | Very Good | Daily use, general purpose |
| **high_accuracy** | large-v3 | float16 | 2 | 8 | Slower | Excellent | Important content, difficult audio |

### Fast Preset

**Goal**: Maximum speed for quick turnaround

```bash
vociferous transcribe file.wav --preset fast
# or
vociferous transcribe file.wav --fast
```

**Configuration**:
- Model: `openai/whisper-large-v3-turbo` (optimized)
- Compute: `int8_float16` (mixed precision)
- Beam size: 1 (greedy decoding)
- Batch size: 16 (large batches for throughput)

**Performance**:
- CPU: ~0.3 RTF (30s audio → 10s processing)
- GPU: ~0.1 RTF (30s audio → 3s processing)

**Accuracy**:
- Word Error Rate (WER): ~3-5% on clean audio
- Slightly lower accuracy than balanced on difficult audio

**When to Use**:
- Quick drafts
- Batch processing many files
- Time-sensitive transcription
- When accuracy is less critical

---

### Balanced Preset (Default)

**Goal**: Best general-purpose balance of speed and accuracy

```bash
vociferous transcribe file.wav --preset balanced
# or simply
vociferous transcribe file.wav
```

**Configuration**:
- Model: `openai/whisper-large-v3-turbo`
- Compute: `auto` (float16 on GPU, int8 on CPU)
- Beam size: 1 (greedy decoding)
- Batch size: 12

**Performance**:
- CPU: ~0.5 RTF (30s audio → 15s processing)
- GPU: ~0.15 RTF (30s audio → 4.5s processing)

**Accuracy**:
- Word Error Rate (WER): ~2-4% on clean audio
- Good performance on most audio conditions

**When to Use**:
- Daily transcription tasks
- General-purpose use
- When you want good speed and accuracy
- Default choice for most users

---

### High-Accuracy Preset

**Goal**: Maximum quality for important transcriptions

```bash
vociferous transcribe interview.wav --preset high_accuracy
```

**Configuration**:
- Model: `openai/whisper-large-v3` (full model, not turbo)
- Compute: `float16` on GPU, `int8` on CPU
- Beam size: 2 (beam search explores multiple hypotheses)
- Batch size: 8 (smaller batches, more careful processing)

**Performance**:
- CPU: ~1.5 RTF (30s audio → 45s processing)
- GPU: ~0.4 RTF (30s audio → 12s processing)

**Accuracy**:
- Word Error Rate (WER): ~1.5-3% on clean audio
- Best performance on difficult audio (accents, noise, technical terms)

**When to Use**:
- Important transcriptions (interviews, legal, medical)
- Publication-quality content
- Difficult audio (background noise, accents)
- When accuracy is paramount

---

## Engine Selection Guide

### Decision Tree

```
Do you need publication-quality punctuation?
├─ Yes → Use Voxtral Local
└─ No → Continue

Is speed your top priority?
├─ Yes → Use Whisper Turbo with Fast preset
└─ No → Continue

Is accuracy critical (legal, medical, publishing)?
├─ Yes → Use Whisper Turbo with High-Accuracy preset
└─ No → Use Whisper Turbo with Balanced preset (default)
```

### Use Case Matrix

| Use Case | Recommended Engine | Recommended Preset |
|----------|-------------------|-------------------|
| Daily meetings | Whisper Turbo | balanced |
| Quick standup notes | Whisper Turbo | fast |
| Batch processing | Whisper Turbo | fast |
| Important interviews | Whisper Turbo | high_accuracy |
| Legal/medical | Whisper Turbo | high_accuracy |
| Publication content | Voxtral Local | N/A |
| Long lectures | Voxtral Local | N/A |
| Difficult audio | Whisper Turbo | high_accuracy |
| Non-English | Whisper Turbo | balanced |

---

## Performance Benchmarks

### Whisper Turbo RTF (Real-Time Factor)

**Note**: These benchmarks are representative examples. Actual performance varies based on your specific hardware, audio characteristics, and system load.

**CPU (Intel i7-12700K, 16 GB RAM)**:

| Preset | RTF | Example (30s audio) |
|--------|-----|---------------------|
| fast | 0.3 | 10s processing |
| balanced | 0.5 | 15s processing |
| high_accuracy | 1.5 | 45s processing |

**GPU (NVIDIA RTX 3060, 12 GB VRAM)**:

| Preset | RTF | Example (30s audio) |
|--------|-----|---------------------|
| fast | 0.1 | 3s processing |
| balanced | 0.15 | 4.5s processing |
| high_accuracy | 0.4 | 12s processing |

*RTF = Processing time / Audio duration. Lower is better.*

### Voxtral Local RTF

**GPU (NVIDIA RTX 3060, 12 GB VRAM)**:
- RTF: ~1.0-2.0 (similar or slower than real-time)
- Example: 30s audio → 30-60s processing

**CPU**: Not recommended (extremely slow, 5-10x slower than GPU)

---

## Memory Requirements

### Whisper Turbo

| Configuration | RAM/VRAM |
|---------------|----------|
| CPU, int8 | 2-4 GB RAM |
| GPU, float16 | 6-8 GB VRAM |
| High-accuracy, GPU | 8-10 GB VRAM |

### Voxtral Local

| Configuration | RAM/VRAM |
|---------------|----------|
| CPU | 12-16 GB RAM (not recommended) |
| GPU | 12-16 GB VRAM |

---

## Advanced Configuration

### Custom Whisper Settings

Override presets in `~/.config/vociferous/config.toml`:

```toml
[whisper]
model = "openai/whisper-large-v3-turbo"
compute_type = "float16"
beam_size = 3  # Higher beam = slower but potentially more accurate
batch_size = 8
temperature = 0.0  # Greedy decoding
```

### Custom Voxtral Settings

```toml
[voxtral]
max_new_tokens = 4096
temperature = 0.2  # Lower = more deterministic
prompt = "You are a professional transcription system."
```

### Fine-Tuning for Your Use Case

**For speed**:
```toml
[whisper]
batch_size = 24  # Larger batches (requires more memory)
compute_type = "int8_float16"  # Mixed precision

[params]
enable_vad = true  # Skip silence
```

**For accuracy**:
```toml
[whisper]
beam_size = 3  # Wider search
temperature = 0.0  # Greedy
compute_type = "float16"  # Full precision

[params]
enable_vad = false  # Process all audio
```

---

## Language Support

### Whisper Turbo Languages

Whisper supports 99 languages. View all with:

```bash
vociferous languages
```

**Most common**:
- English (en)
- Spanish (es)
- French (fr)
- German (de)
- Italian (it)
- Portuguese (pt)
- Russian (ru)
- Chinese (zh)
- Japanese (ja)
- Korean (ko)

**Usage**:
```bash
vociferous transcribe spanish.wav --language es
```

### Voxtral Languages

Currently optimized for English. Other languages may work but are not officially supported.

---

## Next Steps

- **[Configuration](Configuration.md)**: Deep dive into all configuration options
- **[Getting Started](Getting-Started.md)**: Basic usage guide
- **[How It Works](How-It-Works.md)**: Technical architecture details
