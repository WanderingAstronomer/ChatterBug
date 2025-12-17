# Scripts

Utility scripts for installing, running, and managing Vociferous.

## run.py

**Application entry point with GPU library configuration.**

```bash
python scripts/run.py
```

### What it does

1. **Configures GPU libraries** - Sets `LD_LIBRARY_PATH` for CUDA/cuDNN in the venv
2. **Re-executes if needed** - Uses `os.execv()` to restart with correct environment
3. **Sets up Python path** - Adds `src/` to module search path
4. **Configures logging** - Initializes logging before any imports
5. **Launches application** - Imports and runs `main.py`

### Why a separate entry point?

`LD_LIBRARY_PATH` must be set **before** any CUDA libraries are loaded. Python's import system loads shared libraries immediately, so environment changes after import don't work. The re-exec pattern solves this:

```
First run: Check GPU paths → Set LD_LIBRARY_PATH → os.execv() (restart)
Second run: LD_LIBRARY_PATH already set → Import CUDA → Run app
```

### Environment Variables

- `_VOCIFEROUS_ENV_READY` - Sentinel to prevent infinite re-exec loops
- `CUDA_VISIBLE_DEVICES` - Defaults to `0` if not set
- `LD_LIBRARY_PATH` - Prepended with NVIDIA library paths from venv

---

## check_deps.py

**Dependency verification script.**

```bash
python scripts/check_deps.py
```

### Output

```
==============================================================
Vociferous Dependency Check
==============================================================

Required Packages:
--------------------------------------------------------------
  ✓ faster-whisper
  ✓ ctranslate2
  ✓ numpy
  ...

Optional Packages:
--------------------------------------------------------------
  ⚠ some-optional-pkg - not installed (optional)

Development Packages:
--------------------------------------------------------------
  ✓ pytest
  ✓ ruff

==============================================================
```

### Package Categories

| Category | Purpose |
|----------|---------|
| **Required** | Must be installed for app to run |
| **Optional** | Enhance functionality but not required |
| **Development** | Testing and code quality tools |

### Exit Code

- `0` - All required packages present
- `1` - One or more required packages missing

---

## install.sh

**Automated installation script.**

```bash
chmod +x scripts/install.sh
./scripts/install.sh
```

### What it does

1. **Checks Python version** - Warns if not 3.12/3.13
2. **Creates virtual environment** - `.venv/` in project root
3. **Upgrades pip** - Ensures latest pip, setuptools, wheel
4. **Installs dependencies** - `pip install -r requirements.txt`
5. **Verifies installation** - Imports key packages to confirm success

### Output

```
==========================================
Vociferous Installation Script
==========================================

Detected Python version: 3.12
Creating virtual environment...
Activating virtual environment...
Upgrading pip...

==========================================
Installing dependencies
==========================================
...

==========================================
Verifying installation
==========================================
✓ faster-whisper imported successfully
✓ onnxruntime imported successfully
✓ PyQt5 imported successfully
...

==========================================
Installation complete!
==========================================

To run the application:
  source .venv/bin/activate
  python scripts/run.py
```

---

## vociferous.sh (in project root)

**GPU-optimized launcher wrapper.**

```bash
./vociferous.sh
```

Sets environment variables and activates venv before running:
- `LD_LIBRARY_PATH` for CUDA libraries
- `RUST_LOG=error` to suppress Vulkan warnings
- Activates `.venv` automatically
