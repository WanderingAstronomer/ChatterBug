# Troubleshooting

## Common Issues

### Hotkey Not Working (Wayland)

**Symptom:** Pressing the activation key does nothing.

**Cause:** The user is not in the `input` group, required for evdev.

**Solution:**
```bash
sudo usermod -a -G input $USER
# Log out and back in
```

Verify:
```bash
groups | grep input
```

### Hotkey Not Working (X11)

**Symptom:** Key presses not detected on X11.

**Cause:** pynput may need X11 libraries.

**Solution:**
```bash
sudo apt install python3-xlib  # Debian/Ubuntu
```

### CUDA Libraries Not Found

**Symptom:** Warning about CUDA/cuDNN libraries at startup.

**Solution:** Use the wrapper script:
```bash
./vociferous.sh
```

This sets `LD_LIBRARY_PATH` before loading CUDA libraries.

### Model Download Fails

**Symptom:** Network error when downloading Whisper model.

**Solution:**
1. Check internet connection
2. Try again (transient HuggingFace Hub issues)
3. Manually download model:
   ```bash
   python -c "from faster_whisper import WhisperModel; WhisperModel('distil-large-v3')"
   ```

### No Audio Input

**Symptom:** Recording starts but produces empty transcription.

**Causes:**
- Microphone not selected as default
- Microphone muted
- PulseAudio/PipeWire permissions

**Solution:**
```bash
# Check recording devices
pactl list sources short

# Set default source
pactl set-default-source <source_name>

# Test microphone
arecord -d 3 test.wav && aplay test.wav
```

### Transcription is Wrong Language

**Symptom:** English speech transcribed as another language.

**Solution:** Set language explicitly in config:
```yaml
model_options:
  language: en
```

Or use Settings → Model Options → Language.

### GPU Not Used (Slow Transcription)

**Symptom:** Transcription takes 10+ seconds for short clips.

**Check GPU detection:**
```bash
python -c "import ctranslate2; print(ctranslate2.get_cuda_device_count())"
```

If 0, CUDA is not available. Ensure:
- NVIDIA driver installed (`nvidia-smi` works)
- CUDA toolkit matches ctranslate2 requirements
- Using `./vociferous.sh` wrapper

### Permission Denied on /dev/input/*

**Symptom:** evdev backend fails to open devices.

**Solution:**
```bash
# Add user to input group
sudo usermod -a -G input $USER

# Verify group membership after re-login
ls -la /dev/input/event*
```

### Qt Platform Plugin Error

**Symptom:** "Could not load the Qt platform plugin"

**Solution:**
```bash
# Ensure Qt dependencies are installed
sudo apt install libxcb-xinerama0 libxkbcommon-x11-0

# For Wayland
export QT_QPA_PLATFORM=wayland
```

## Debug Mode

For detailed logging:
```bash
export VOCIFEROUS_DEBUG=1
python scripts/run.py
```

This enables DEBUG level logging for all modules.

## Reporting Issues

When reporting bugs, include:
1. Output of `python scripts/check_deps.py`
2. Session type: `echo $XDG_SESSION_TYPE`
3. Python version: `python3 --version`
4. GPU info: `nvidia-smi` (if applicable)
5. Console output with error message
