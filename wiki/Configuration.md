# Configuration

Vociferous provides extensive configuration options through config files, environment variables, and CLI flags. This page covers all configuration mechanisms and options.

## Configuration Hierarchy

Settings are applied in order of priority (highest to lowest):

1. **CLI flags**: `--engine whisper_turbo`, `--device cuda`, etc.
2. **Environment variables**: `VOCIFEROUS_ENGINE`, `VOCIFEROUS_DEVICE`
3. **Config file**: `~/.config/vociferous/config.toml`
4. **Built-in defaults**: Sensible defaults for first-time use

## Config File Location

**Primary location**: `~/.config/vociferous/config.toml`

This file is automatically created on first run with default values. Edit it to customize Vociferous behavior.

### Example Config File

```toml
# Vociferous Configuration

# Default transcription engine
# Options: whisper_turbo, voxtral_local, parakeet_rnnt
engine = "whisper_turbo"

# Compute device
# Options: cpu, cuda, auto (auto detects CUDA if available)
device = "auto"

# Model cache directory
# Models are downloaded here and reused
model_cache_dir = "~/.cache/vociferous/models"

# History storage location
history_dir = "~/.cache/vociferous/history"

# Maximum history entries to retain (0 = unlimited)
max_history_entries = 100

[params]
# Default language for transcription
# Options: en, es, fr, de, it, etc. or "auto" for detection
language = "en"

# Quality preset (whisper_turbo only)
# Options: fast, balanced, high_accuracy
preset = "balanced"

# Enable voice activity detection (VAD)
# Removes silence, speeds up processing
enable_vad = true

# Clean disfluencies (um, uh, etc.)
clean_disfluencies = true

# Enable word-level timestamps
word_timestamps = false

# Save transcriptions to history
save_history = true

[whisper]
# Whisper-specific settings (overrides presets)
model = "openai/whisper-large-v3-turbo"
compute_type = "auto"  # auto, float16, int8, int8_float16
beam_size = 1
batch_size = 12
temperature = 0.0  # 0.0 = greedy, higher = more random

[voxtral]
# Voxtral-specific settings
max_new_tokens = 4096
temperature = 0.2
prompt = ""

[polish]
# Grammar/fluency polishing settings
enabled = false
model = "NousResearch/Hermes-3-Llama-3.1-8B-GGUF"
max_tokens = 4096
temperature = 0.3
gpu_layers = 0  # Number of layers to offload to GPU (0 = CPU only)
context_length = 8192
```

## Configuration Options Reference

### Top-Level Settings

#### `engine`
- **Type**: String
- **Default**: `"whisper_turbo"`
- **Options**: `whisper_turbo`, `voxtral_local`, `parakeet_rnnt`
- **Description**: Default transcription engine
- **CLI Override**: `--engine` or `-e`
- **Env Variable**: `VOCIFEROUS_ENGINE`

#### `device`
- **Type**: String
- **Default**: `"auto"`
- **Options**: `cpu`, `cuda`, `auto`
- **Description**: Compute device for inference
- **CLI Override**: `--device`
- **Env Variable**: `VOCIFEROUS_DEVICE`

#### `model_cache_dir`
- **Type**: Path
- **Default**: `"~/.cache/vociferous/models"`
- **Description**: Directory for cached models
- **CLI Override**: N/A (config file only)
- **Env Variable**: `VOCIFEROUS_MODEL_CACHE_DIR`

#### `history_dir`
- **Type**: Path
- **Default**: `"~/.cache/vociferous/history"`
- **Description**: Directory for transcription history
- **CLI Override**: N/A (config file only)
- **Env Variable**: `VOCIFEROUS_HISTORY_DIR`

#### `max_history_entries`
- **Type**: Integer
- **Default**: `100`
- **Description**: Maximum history entries to retain (0 = unlimited)
- **CLI Override**: N/A (config file only)

### `[params]` Section

Common parameters applied to all engines.

#### `language`
- **Type**: String
- **Default**: `"en"`
- **Options**: ISO 639-1 codes (`en`, `es`, `fr`, etc.) or `auto`
- **Description**: Language for transcription
- **CLI Override**: `--language` or `-l`

#### `preset`
- **Type**: String
- **Default**: `"balanced"`
- **Options**: `fast`, `balanced`, `high_accuracy`
- **Description**: Quality preset (whisper_turbo only)
- **CLI Override**: `--preset` or `-p`

#### `enable_vad`
- **Type**: Boolean
- **Default**: `true`
- **Description**: Enable voice activity detection
- **CLI Override**: `--vad-filter` / `--no-vad-filter`

#### `clean_disfluencies`
- **Type**: Boolean
- **Default**: `true`
- **Description**: Remove filler words (um, uh, etc.)
- **CLI Override**: `--clean-disfluencies` / `--no-clean-disfluencies`

#### `word_timestamps`
- **Type**: Boolean
- **Default**: `false`
- **Description**: Include word-level timestamps in output
- **CLI Override**: `--word-timestamps`

#### `save_history`
- **Type**: Boolean
- **Default**: `true`
- **Description**: Save transcriptions to history
- **CLI Override**: `--save-history` / `--no-save-history`

### `[whisper]` Section

Whisper Turbo engine-specific settings. These override preset defaults.

#### `model`
- **Type**: String
- **Default**: `"openai/whisper-large-v3-turbo"` (balanced preset)
- **Description**: Whisper model identifier
- **Options**: 
  - `openai/whisper-large-v3-turbo` (optimized, fast)
  - `openai/whisper-large-v3` (full model, high accuracy)
  - `openai/whisper-large-v2`
  - Other compatible Whisper models

#### `compute_type`
- **Type**: String
- **Default**: `"auto"` (float16 on GPU, int8 on CPU)
- **Options**: `auto`, `float16`, `int8`, `int8_float16`
- **Description**: Precision for inference

#### `beam_size`
- **Type**: Integer
- **Default**: `1` (greedy decoding)
- **Description**: Beam search width (higher = slower but potentially more accurate)
- **CLI Override**: `--beam-size`

#### `batch_size`
- **Type**: Integer
- **Default**: `12` (balanced preset)
- **Description**: Batch size for processing
- **CLI Override**: `--batch-size`

#### `temperature`
- **Type**: Float
- **Default**: `0.0`
- **Description**: Sampling temperature (0.0 = greedy, higher = more random)
- **CLI Override**: `--whisper-temperature`

### `[voxtral]` Section

Voxtral engine-specific settings.

#### `max_new_tokens`
- **Type**: Integer
- **Default**: `4096`
- **Description**: Maximum tokens to generate
- **CLI Override**: `--max-new-tokens`

#### `temperature`
- **Type**: Float
- **Default**: `0.2`
- **Description**: Sampling temperature for generation
- **CLI Override**: `--gen-temperature`

#### `prompt`
- **Type**: String
- **Default**: `""`
- **Description**: System prompt for Voxtral
- **CLI Override**: `--prompt`

### `[polish]` Section

Grammar and fluency polishing settings (requires `[polish]` extra).

#### `enabled`
- **Type**: Boolean
- **Default**: `false`
- **Description**: Enable post-transcription polishing
- **CLI Override**: `--polish` / `--no-polish`

#### `model`
- **Type**: String
- **Default**: `"NousResearch/Hermes-3-Llama-3.1-8B-GGUF"`
- **Description**: llama.cpp model for polishing
- **CLI Override**: `--polish-model`

#### `max_tokens`
- **Type**: Integer
- **Default**: `4096`
- **Description**: Maximum tokens for polishing
- **CLI Override**: `--polish-max-tokens`

#### `temperature`
- **Type**: Float
- **Default**: `0.3`
- **Description**: Sampling temperature for polishing
- **CLI Override**: `--polish-temperature`

#### `gpu_layers`
- **Type**: Integer
- **Default**: `0` (CPU only)
- **Description**: Number of model layers to offload to GPU
- **CLI Override**: `--polish-gpu-layers`

#### `context_length`
- **Type**: Integer
- **Default**: `8192`
- **Description**: Context window size for polishing model
- **CLI Override**: `--polish-context-length`

## Environment Variables

All config file settings can be overridden with environment variables:

```bash
# General settings
export VOCIFEROUS_ENGINE="whisper_turbo"
export VOCIFEROUS_DEVICE="cuda"
export VOCIFEROUS_MODEL_CACHE_DIR="/custom/cache/path"

# Parameters
export VOCIFEROUS_LANGUAGE="es"
export VOCIFEROUS_PRESET="high_accuracy"

# Whisper settings
export VOCIFEROUS_WHISPER_MODEL="openai/whisper-large-v3"
export VOCIFEROUS_WHISPER_BEAM_SIZE="2"

# Run transcription with env vars
vociferous transcribe meeting.wav
```

Environment variable naming: `VOCIFEROUS_<SECTION>_<KEY>` in uppercase.

## CLI Flags Reference

CLI flags have the highest priority and override all other settings.

### Common Flags

```bash
# Engine and device
-e, --engine [whisper_turbo|voxtral_local]
--device [cpu|cuda|auto]

# Language and quality
-l, --language <code>       # en, es, fr, etc. or auto
-p, --preset <name>         # fast, balanced, high_accuracy
--fast                      # Shortcut for --preset fast

# Output
-o, --output <path>         # Save to file
--clipboard                 # Copy to clipboard

# Processing options
--vad-filter / --no-vad-filter
--clean-disfluencies / --no-clean-disfluencies
--word-timestamps
--save-history / --no-save-history

# Whisper-specific
--beam-size <int>
--batch-size <int>
--whisper-temperature <float>

# Voxtral-specific
--prompt <text>
--max-new-tokens <int>
--gen-temperature <float>

# Polish-specific
--polish / --no-polish
--polish-model <name>
--polish-max-tokens <int>
--polish-temperature <float>
--polish-gpu-layers <int>
```

### Examples

```bash
# Override engine
vociferous transcribe file.wav --engine voxtral_local

# Override device
vociferous transcribe file.wav --device cuda

# Override language and preset
vociferous transcribe file.wav -l es -p high_accuracy

# Combine multiple overrides
vociferous transcribe file.wav \
    --engine whisper_turbo \
    --preset fast \
    --device cpu \
    --language en \
    --output transcript.txt
```

## Presets Deep Dive

Presets are convenience bundles for common use cases (whisper_turbo only).

### `fast` Preset
**Goal**: Maximum speed for quick drafts

```toml
model = "openai/whisper-large-v3-turbo"
compute_type = "int8_float16"  # Mixed precision
beam_size = 1                   # Greedy decoding
batch_size = 16                 # Large batches
```

**Best for**: Quick turnaround, drafts, batch processing

### `balanced` Preset (Default)
**Goal**: Good balance of speed and accuracy

```toml
model = "openai/whisper-large-v3-turbo"
compute_type = "auto"  # float16 on GPU, int8 on CPU
beam_size = 1
batch_size = 12
```

**Best for**: General-purpose transcription, daily use

### `high_accuracy` Preset
**Goal**: Maximum quality for important transcriptions

```toml
model = "openai/whisper-large-v3"  # Full model, not turbo
compute_type = "float16"           # High precision
beam_size = 2                      # Beam search
batch_size = 8                     # Smaller batches
```

**Best for**: Important content, publishing, difficult audio

## Custom Configurations

### Per-Project Config

Create project-specific configs:

```bash
# Create project directory
mkdir my_project
cd my_project

# Create local config (using heredoc - text between << EOF and EOF is written to file)
cat > vociferous.toml << 'EOF'
engine = "whisper_turbo"
device = "cuda"

[params]
language = "en"
preset = "high_accuracy"
save_history = false
EOF

# Use with VOCIFEROUS_CONFIG env var
export VOCIFEROUS_CONFIG="./vociferous.toml"
vociferous transcribe audio.wav
```

### Language-Specific Configs

```bash
# Spanish transcription profile
cat > ~/.config/vociferous/spanish.toml << 'EOF'
[params]
language = "es"
preset = "balanced"
clean_disfluencies = true
EOF

# Use with -c/--config flag
vociferous transcribe spanish_meeting.wav --config spanish.toml
```

### GPU Optimization

```toml
# Maximize GPU usage
device = "cuda"

[whisper]
compute_type = "float16"
batch_size = 24  # Larger batches for GPU

[polish]
gpu_layers = 35  # Offload all polish layers to GPU
```

### CPU Optimization

```toml
# Optimize for CPU
device = "cpu"

[whisper]
compute_type = "int8"  # Quantized for CPU efficiency
batch_size = 4         # Smaller batches for CPU

[params]
enable_vad = true  # Reduce processing time
```

## Next Steps

- **[Engines & Presets](Engines-and-Presets.md)**: Understand engines and quality settings
- **[How It Works](How-It-Works.md)**: Learn about the architecture
- **[Getting Started](Getting-Started.md)**: Basic usage guide
