# Installation Guide

## Quick Install

```bash
chmod +x scripts/install.sh
./scripts/install.sh
```

This creates a virtual environment, installs all dependencies, and verifies the installation.

## Manual Installation

### 1. Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. System Dependencies

#### For Wayland (recommended)

```bash
# Clipboard support
sudo apt install wl-clipboard  # Debian/Ubuntu
sudo pacman -S wl-clipboard     # Arch

# Add user to input group (required for evdev backend)
sudo usermod -a -G input $USER
# Log out and back in for group change to take effect
```

#### For X11

```bash
sudo apt install python3-xlib  # Debian/Ubuntu
```

### 4. GPU Setup (Optional)

For CUDA acceleration, ensure you have:
- NVIDIA GPU with compute capability 5.0+
- CUDA Toolkit 11.8+ or 12.x
- cuDNN 8.x matching your CUDA version

The `./vociferous.sh` wrapper automatically configures `LD_LIBRARY_PATH` for GPU libraries in the virtual environment.

## Verify Installation

```bash
python scripts/check_deps.py
```

This checks all required packages are importable and reports any missing dependencies.

## Running the Application

### GPU Mode (Recommended)

```bash
./vociferous.sh
```

This wrapper:
- Sets `LD_LIBRARY_PATH` for CUDA libraries in the venv
- Suppresses verbose Vulkan warnings with `RUST_LOG=error`
- Activates the virtual environment

### CPU Mode

```bash
python scripts/run.py
```

If you see CUDA library warnings, use `./vociferous.sh` instead.

## First Run

1. The Whisper model downloads on first launch (~1.5GB for distil-large-v3)
2. Main window appears with history sidebar
3. System tray icon appears
4. Press Right Alt (default) to start recording

## Updating

```bash
git pull
pip install -r requirements.txt
```
