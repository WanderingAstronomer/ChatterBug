# Vociferous GUI - KivyMD Interface

The Vociferous GUI is the graphical user interface for Vociferous, built with KivyMD to provide an intuitive, modern interface for AI-powered transcription.

## Features

### First-Run Setup
- **Splash Screen**: Welcome screen on first launch
- **Hardware Selection**: Choose between GPU (CUDA), CPU, or Both modes
- **Automatic Dependency Installation**: Install appropriate dependencies based on hardware selection

### Main Interface
- **Dark Theme**: Modern dark theme with bright blue accents
- **Navigation Drawer**: Left-side vertical navigation pane for easy access to different sections
- **Home Screen**: Simple file selection and transcription interface
- **Settings Screen**: Comprehensive settings panel with all CLI options

### Settings
All CLI options are available in the GUI settings panel:
- **Engine Configuration**
  - Engine selection (whisper_turbo, voxtral_local)
  - Model selection
  - Device selection (auto, cpu, cuda)
  - Compute type configuration

- **Transcription Options**
  - Voice Activity Detection (VAD) toggle
  - Batching enable/disable
  - Word timestamps
  - Batch size adjustment

- **Advanced Options**
  - All advanced CLI parameters accessible
  - Inline settings with clear labels
  - Hover tooltips for guidance

## Installation

### Base Installation
```bash
# Install Vociferous with GUI support
pip install -e .[gui]
```

### Separate GPU/CPU Installation (Alternative)
The GUI provides an installer at first run, but you can also install manually:

```bash
# For GPU users
pip install -e .[gui]
# GPU dependencies are already included in base install

# For CPU-only users
pip install -e .[gui]
# Remove GPU-specific packages if needed:
pip uninstall nvidia-cudnn-cu12
```

## Usage

### Launch the GUI
```bash
vociferous-gui
```

Or from Python:
```python
from vociferous.gui.app import run_gui
run_gui()
```

### First Run
On first launch, the Vociferous GUI will:
1. Show a welcome splash screen
2. Ask you to select your hardware configuration (GPU/CPU/Both)
3. Install appropriate dependencies
4. Take you to the main application

### Subsequent Runs
After first setup, the Vociferous GUI launches directly to the main interface.

## Architecture

### Color Scheme
- **Primary**: Dark background (#1E1E1E)
- **Accent**: Bright blue tones (#4A9EFF, #1A5FBF)
- **Navigation**: Blue highlights for active items
- **Text**: White/light gray for high contrast

### Screen Structure
```
VociferousGUIApp
├── SplashScreen (first run only)
│   ├── Welcome message
│   ├── Hardware selection buttons
│   └── Installation progress
└── Main App
    ├── Navigation Drawer (left side)
    │   ├── Home
    │   └── Settings
    └── Content Area
        ├── Top App Bar (bright blue)
        └── Screen Manager
            ├── HomeScreen
            │   ├── File selection
            │   ├── Transcription controls
            │   └── Output display
            └── SettingsScreen
                ├── Engine configuration
                ├── Transcription options
                └── Advanced settings
```

## Development

### Code Structure
```
vociferous/gui/
├── __init__.py          # Package initialization
├── app.py               # Main KivyMD application
├── splash.py            # Splash screen for first-run setup
├── screens.py           # HomeScreen and SettingsScreen
└── installer.py         # Dependency installation logic
```

### Key Components

**VociferousGUIApp** (`app.py`)
- Main application class
- Handles screen management
- Configures theme and window

**SplashScreen** (`splash.py`)
- First-run welcome screen
- Hardware configuration selection
- Dependency installation

**HomeScreen** (`screens.py`)
- File selection interface
- Transcription controls
- Output display

**SettingsScreen** (`screens.py`)
- All CLI options as GUI controls
- Category organization
- Real-time configuration updates

**DependencyInstaller** (`installer.py`)
- Handles GPU/CPU dependency installation
- Checks installation status
- Manages pip installations

## Dependencies

### Required (GUI)
- `kivymd>=1.2.0` - Material Design components for Kivy
- `kivy>=2.3.0` - Cross-platform GUI framework
- `pillow>=10.0.0` - Image processing

### Base Vociferous
All base Vociferous dependencies are required (see main README.md)

## Configuration

Configuration is shared with Vociferous CLI:
- Config file: `~/.config/vociferous/config.toml`
- GUI setup marker: `~/.config/vociferous/.gui_setup_complete`
- Model cache: `~/.cache/vociferous/models`

## Troubleshooting

### "Module not found: kivymd"
```bash
pip install -e .[gui]
```

### Window doesn't appear
Check that you have the required system dependencies for Kivy:
- **Linux**: `python3-dev`, `build-essential`, SDL2 libraries
- **macOS**: Usually works out of the box
- **Windows**: Usually works out of the box

### First-run setup stuck
If the installation hangs, you can:
1. Close the app
2. Remove the marker: `rm ~/.config/vociferous/.gui_setup_complete`
3. Install dependencies manually: `pip install torch nvidia-cudnn-cu12`
4. Relaunch the Vociferous GUI

## Future Enhancements

Planned features for future versions:
- Real-time transcription progress visualization
- Waveform display
- History browser in GUI
- Drag-and-drop file selection
- Batch transcription queue
- Export options (txt, srt, vtt)
- Custom theme selection
- Keyboard shortcuts
- Multi-window support

## License

Same as Vociferous - see LICENSE file in the root directory.
