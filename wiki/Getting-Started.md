# Getting Started

This guide will help you install Vociferous and run your first transcription in minutes.

## Prerequisites

Before installing Vociferous, ensure you have:

### Required
- **Python 3.11 or later**: Check with `python --version`
- **pip**: Python package installer
- **ffmpeg**: Audio decoding library
  - **macOS**: `brew install ffmpeg`
  - **Ubuntu/Debian**: `sudo apt install ffmpeg`
  - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH

### Optional
- **CUDA-capable GPU**: For faster transcription (NVIDIA GPU with CUDA support)
- **16+ GB RAM**: Recommended for high-accuracy preset and long audio files

### Verify Prerequisites

```bash
# Check Python version (should be 3.11+)
python --version

# Check ffmpeg installation
ffmpeg -version

# Check for CUDA (optional)
nvidia-smi
```

## Installation

### 1. Clone or Download Repository

```bash
git clone https://github.com/WanderingAstronomer/Vociferous.git
cd Vociferous
```

### 2. Install Base Package

```bash
pip install -e .
```

This installs:
- Core transcription functionality
- Whisper Turbo engine (faster-whisper + CTranslate2)
- Silero VAD for voice activity detection
- CLI tools (`vociferous` command)

### 3. Install Optional Extras (As Needed)

#### GUI Interface
For graphical user interface with drag-and-drop:
```bash
pip install -e .[gui]
```

#### Polishing/Grammar Enhancement
For post-processing with llama.cpp models:
```bash
pip install -e .[polish]
```

#### Voxtral Engine
For advanced punctuation and long-context transcription:
```bash
pip install -e .[voxtral]
```

#### Development Tools
For running tests and type checking:
```bash
pip install -e .[dev]
```

#### Install All Extras
To install everything:
```bash
pip install -e .[gui,polish,voxtral,dev]
```

### 4. Verify Installation

```bash
# Check installation and prerequisites
vociferous check

# List supported languages
vociferous languages
```

## Your First Transcription

### Transcribe an Audio File

The simplest way to use Vociferous:

```bash
vociferous transcribe path/to/audio.wav
```

The transcript will be printed to your terminal (stdout).

### Save Transcript to File

```bash
vociferous transcribe meeting.mp3 --output transcript.txt
```

Or use output redirection:

```bash
vociferous transcribe meeting.mp3 > transcript.txt
```

### Specify Language

For non-English audio:

```bash
vociferous transcribe spanish_meeting.wav --language es
```

Use `auto` for automatic language detection:

```bash
vociferous transcribe unknown.wav --language auto
```

See all supported languages:
```bash
vociferous languages
```

### Choose a Quality Preset

Vociferous offers three quality presets:

```bash
# Fast (quickest processing, slightly lower accuracy)
vociferous transcribe podcast.mp3 --preset fast

# Balanced (default - good speed and accuracy)
vociferous transcribe meeting.wav --preset balanced

# High-accuracy (best quality, slower processing)
vociferous transcribe interview.wav --preset high_accuracy
```

See [Engines & Presets](Engines-and-Presets.md) for detailed information.

## Common Use Cases

### Batch Transcription

Transcribe multiple files:

```bash
# Process all WAV files in a directory (using find to handle empty directories)
find audio/ -name "*.wav" -type f -exec sh -c '
    vociferous transcribe "$1" -o "transcripts/$(basename "$1" .wav).txt"
' sh {} \;
```

Alternative using bash with null glob handling:

```bash
# Enable nullglob to handle case where no files match
shopt -s nullglob
for file in audio/*.wav; do
    vociferous transcribe "$file" -o "transcripts/$(basename "$file" .wav).txt"
done
```

### Quick Transcription with Default Settings

```bash
vociferous transcribe recording.wav
```

### High-Quality Transcription for Publishing

```bash
vociferous transcribe interview.wav \
    --preset high_accuracy \
    --language en \
    --output interview_transcript.txt
```

### Using Voxtral for Better Punctuation

```bash
# Requires [voxtral] extra
vociferous transcribe lecture.mp3 \
    --engine voxtral_local \
    --language en \
    --output lecture_notes.txt
```

### Copy Transcript to Clipboard

```bash
vociferous transcribe standup.wav --clipboard
```

## GUI Usage

If you installed the `[gui]` extra:

```bash
vociferous-gui
```

The GUI provides:
- **Drag-and-drop**: Drop audio files to transcribe
- **Recording**: Record from microphone
- **History**: View past transcriptions
- **Settings**: Configure engines, presets, and options
- **Copy/Export**: Easy clipboard and file export

See [QUICKSTART_GUI.md](../QUICKSTART_GUI.md) for detailed GUI instructions.

## Configuration

Vociferous uses sensible defaults, but you can customize behavior:

### First Run

On first run, Vociferous creates:
- Config file: `~/.config/vociferous/config.toml`
- Model cache: `~/.cache/vociferous/models/`
- History storage: `~/.cache/vociferous/history/`

### Quick Config Changes

Edit `~/.config/vociferous/config.toml`:

```toml
# Default engine
engine = "whisper_turbo"

# Device (cpu, cuda, or auto)
device = "auto"

# Model cache location
model_cache_dir = "~/.cache/vociferous/models"

[params]
# Default language (en, es, fr, etc. or auto)
language = "en"

# Quality preset (fast, balanced, high_accuracy)
preset = "balanced"

# Voice activity detection (true/false)
enable_vad = true

# Clean filler words (true/false)
clean_disfluencies = true
```

See [Configuration](Configuration.md) for comprehensive configuration options.

## Model Downloads

Models are automatically downloaded on first use:

### Whisper Turbo Models
- **Location**: `~/.cache/vociferous/models/`
- **Size**: ~1.5 GB (turbo), ~3 GB (large-v3)
- **Source**: HuggingFace (CTranslate2 format)

First transcription will take longer as models download. Subsequent runs use cached models.

### Voxtral Models
If using `voxtral_local` engine:
- **Size**: ~14 GB
- Automatically downloaded on first use with Voxtral engine

## Troubleshooting

### "ffmpeg not found"
Install ffmpeg for your OS (see Prerequisites above).

### "Model download failed"
Check internet connection. Models are downloaded from HuggingFace on first use.

### "CUDA out of memory"
Try:
1. Use CPU: `vociferous transcribe file.wav --device cpu`
2. Use fast preset: `vociferous transcribe file.wav --preset fast`
3. Process shorter segments

### "ImportError: No module named X"
Install the relevant optional extra:
- GUI issues: `pip install -e .[gui]`
- Voxtral issues: `pip install -e .[voxtral]`
- Polish issues: `pip install -e .[polish]`

### Slow Performance on CPU
This is expected. For faster processing:
1. Use fast preset: `--preset fast`
2. Enable GPU if available: `--device cuda`
3. Disable VAD if needed: `--no-vad-filter`

### Poor Transcription Quality
Try:
1. Use high-accuracy preset: `--preset high_accuracy`
2. Specify language: `--language en` (don't rely on auto-detection)
3. Ensure audio quality is good (clear speech, minimal background noise)
4. Try Voxtral engine for better punctuation: `--engine voxtral_local`

## Next Steps

Now that you have Vociferous installed and working:

- **[Configuration](Configuration.md)**: Deep dive into configuration options
- **[Engines & Presets](Engines-and-Presets.md)**: Understand engines and quality settings
- **[How It Works](How-It-Works.md)**: Learn about the architecture
- **[Development](Development.md)**: Contribute to the project

## Quick Reference

### Most Common Commands

```bash
# Basic transcription
vociferous transcribe file.wav

# Fast mode
vociferous transcribe file.mp3 --fast

# Save to file
vociferous transcribe file.mp3 -o output.txt

# Different language
vociferous transcribe file.wav -l es

# High quality
vociferous transcribe file.wav -p high_accuracy

# Launch GUI
vociferous-gui

# Check prerequisites
vociferous check

# List languages
vociferous languages
```

### Command Flags Cheat Sheet

| Flag | Description | Example |
|------|-------------|---------|
| `-e`, `--engine` | Choose engine | `-e voxtral_local` |
| `-l`, `--language` | Set language | `-l en` |
| `-o`, `--output` | Output file | `-o transcript.txt` |
| `-p`, `--preset` | Quality preset | `-p high_accuracy` |
| `--fast` | Fast preset shortcut | `--fast` |
| `--clipboard` | Copy to clipboard | `--clipboard` |
| `--device` | Set device | `--device cuda` |
| `--no-vad-filter` | Disable VAD | `--no-vad-filter` |

See `vociferous transcribe --help` for all options.
