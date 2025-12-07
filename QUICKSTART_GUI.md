# Luciferous Quick Start Guide

Welcome to Luciferous, the graphical user interface for Vociferous! This guide will help you get started quickly.

## Installation

### Step 1: Install Vociferous with GUI support

```bash
pip install -e .[gui]
```

This will install:
- KivyMD (Material Design components)
- Kivy (GUI framework)
- All base Vociferous dependencies

### Step 2: Launch Luciferous

```bash
luciferous
```

Or from Python:
```python
from vociferous.gui.app import run_gui
run_gui()
```

## First Run Setup

When you launch Luciferous for the first time, you'll see a splash screen that asks you to select your hardware configuration:

### Hardware Options

1. **GPU (NVIDIA CUDA)**
   - Select this if you have an NVIDIA GPU with CUDA support
   - Provides faster transcription with GPU acceleration
   - Recommended for processing multiple or long audio files

2. **CPU Only**
   - Select this if you don't have a GPU or prefer CPU processing
   - Works on any system but slower than GPU
   - Good for occasional transcription tasks

3. **Both (Flexible)**
   - Installs support for both GPU and CPU
   - Automatically uses GPU when available, falls back to CPU
   - Best option if you're unsure or use multiple machines

### Installation Process

After selecting your hardware, Luciferous will:
1. Download and install necessary dependencies
2. Configure your system for optimal performance
3. Create configuration files
4. Take you to the main application

This setup only happens once. Subsequent launches go directly to the main interface.

## Main Interface

### Navigation

The main window consists of:

**Left Navigation Pane** (vertical)
- Home - File selection and transcription
- Settings - Configuration options

**Top App Bar** (bright blue)
- Menu button to toggle navigation
- Application title

**Content Area**
- Changes based on selected navigation item

### Home Screen

The Home screen is where you transcribe audio files:

1. **Browse Files**
   - Click to open file browser
   - Select an audio file (.wav, .mp3, .flac, .m4a, etc.)
   - File path will appear in the text field

2. **Start Transcription**
   - Click to begin transcribing the selected file
   - Progress updates appear in real-time
   - Transcript appears in the output area

3. **Transcript Output**
   - View the transcribed text
   - Copy/paste as needed
   - Scroll for long transcripts

### Settings Screen

Configure all aspects of transcription:

#### Engine Configuration
- **Engine**: Choose transcription engine
  - `whisper_turbo` - Fast, accurate, offline (default)
  - `voxtral_local` - Smart punctuation, Mistral-based
  - `whisper_vllm` - Server-based (requires vLLM)
  - `voxtral_vllm` - Server-based smart mode

- **Model**: Select AI model (depends on engine)
- **Device**: Choose CPU or CUDA (auto-detects by default)

#### Transcription Options
- **Voice Activity Detection**: Filter out silence
- **Enable Batching**: Process multiple chunks at once
- **Word Timestamps**: Include timing for each word
- **Batch Size**: Number of chunks to process together

#### Advanced Settings
- **Compute Type**: Precision level (int8, float16, etc.)
- More options available as needed

**Save Settings** button persists your configuration.

## Common Workflows

### Basic Transcription

1. Launch Luciferous: `luciferous`
2. Click "Browse Files"
3. Select your audio file
4. Click "Start Transcription"
5. Wait for completion
6. Copy transcript from output area

### Changing Settings

1. Open navigation (menu button)
2. Select "Settings"
3. Modify options as needed
4. Click "Save Settings"
5. Return to "Home" to transcribe with new settings

### GPU vs CPU

The application automatically uses your configured device (GPU or CPU). To change:

1. Go to Settings
2. Click on "Device"
3. Select: `auto`, `cpu`, or `cuda`
4. Save settings
5. Next transcription uses the new device

## Troubleshooting

### "Module not found: kivymd"

```bash
pip install -e .[gui]
```

Make sure you installed with the `[gui]` extra.

### Window doesn't appear

Install system dependencies for Kivy:

**Ubuntu/Debian:**
```bash
sudo apt install python3-dev build-essential libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev
```

**macOS:**
Usually works out of the box. If not:
```bash
brew install sdl2 sdl2_image sdl2_mixer sdl2_ttf
```

### First-run setup stuck

1. Close the application
2. Remove setup marker: `rm ~/.config/vociferous/.gui_setup_complete`
3. Install dependencies manually: `pip install torch`
4. Relaunch: `luciferous`

### Transcription fails

1. Check Settings → Engine is valid
2. Ensure audio file is supported format
3. Check Settings → Device matches your hardware
4. Try CPU mode if GPU fails

### Configuration not saving

Make sure config directory is writable:
```bash
ls -la ~/.config/vociferous/
```

If it doesn't exist:
```bash
mkdir -p ~/.config/vociferous
```

## File Formats

Supported audio formats:
- WAV (.wav)
- MP3 (.mp3)
- FLAC (.flac)
- M4A (.m4a)
- OGG (.ogg)
- Opus (.opus)
- AAC (.aac)
- WMA (.wma)

Any format supported by FFmpeg should work.

## Performance Tips

### For Best Speed:
1. Use GPU mode (NVIDIA CUDA)
2. Enable batching in Settings
3. Use `whisper_turbo` engine
4. Select "fast" preset (when available)

### For Best Accuracy:
1. Use `whisper_vllm` engine with server
2. Select "high_accuracy" preset
3. Disable batching if needed
4. Enable VAD filtering

### For Long Files:
1. Enable batching
2. Increase batch size
3. Use GPU if available
4. Consider breaking into smaller chunks

## Next Steps

- Explore different engines and models
- Experiment with settings for your use case
- Try batch transcription (planned feature)
- Check out the full documentation in `vociferous/gui/README.md`

## Getting Help

- Check the main README: `README.md`
- Review architecture docs: `Planning and Documentation/`
- Report issues on GitHub
- Check logs: `~/.cache/vociferous/`

## Configuration Files

- Config: `~/.config/vociferous/config.toml`
- GUI setup marker: `~/.config/vociferous/.gui_setup_complete`
- Model cache: `~/.cache/vociferous/models/`
- History: `~/.cache/vociferous/history/`

Enjoy transcribing with Luciferous! 🎙️✨
