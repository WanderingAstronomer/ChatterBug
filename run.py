#!/usr/bin/env python3
"""
Vociferous - Application Entry Point.

This is the bootstrap script that sets up the environment and launches
the main application. It handles GPU library paths before any CUDA
libraries are loaded.

Why a Separate Entry Point?
---------------------------
The main application is in `src/main.py`, but we need this script to:
1. Configure LD_LIBRARY_PATH for GPU libraries
2. Set up Python path to find `src/` modules
3. Configure logging before any other code runs

The key insight is that LD_LIBRARY_PATH must be set BEFORE the process
loads any CUDA/cuDNN libraries. Setting it after import won't work.

Process Re-execution Pattern:
-----------------------------
```
┌─────────────────────────────────────────────────────────────────┐
│  First Execution (LD_LIBRARY_PATH not set)                      │
├─────────────────────────────────────────────────────────────────┤
│  1. Check if NVIDIA libs exist in venv                          │
│  2. Set LD_LIBRARY_PATH with cuDNN + cuBLAS paths               │
│  3. Set sentinel env var _VOCIFEROUS_ENV_READY=1                │
│  4. os.execv() → replaces process with new instance             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Second Execution (LD_LIBRARY_PATH set, sentinel present)       │
├─────────────────────────────────────────────────────────────────┤
│  1. Check sentinel → skip re-exec                               │
│  2. Import main (loads CUDA with correct paths)                 │
│  3. Run application                                             │
└─────────────────────────────────────────────────────────────────┘
```

The sentinel prevents infinite re-execution loops.

os.execv() vs subprocess:
-------------------------
`os.execv(executable, args)` REPLACES the current process entirely.
The PID stays the same, but the code is different. This is cleaner
than spawning a subprocess:
- No parent process to manage
- Same PID (for process managers)
- No IPC needed

Path Discovery:
---------------
```python
python_dirs = list(lib_path.glob('python3.*'))
site_packages = python_dirs[0] / 'site-packages' / 'nvidia'
```

NVIDIA installs CUDA libraries into the venv's site-packages. We use
glob to find the Python version directory (3.11, 3.12, etc.) without
hardcoding it.

Why setdefault for CUDA_VISIBLE_DEVICES?
----------------------------------------
```python
os.environ.setdefault('CUDA_VISIBLE_DEVICES', '0')
```

setdefault only sets if not already set. This lets users override
which GPU to use via environment variable while providing a sensible
default (first GPU).

Logging Configuration:
----------------------
Configured BEFORE imports to catch early log messages. Format includes
time, level, logger name, and message for debugging.

Python 3.12+ Features:
----------------------
- Pathlib throughout (no os.path)
- f-strings for path concatenation
- Unpacking in function calls (`*sys.argv`)
"""
import logging
import os
import sys
from pathlib import Path


def _configure_logging() -> None:
    """
    Configure application-wide logging.

    Called before any other code to ensure all log messages are captured.
    Uses a simple console format suitable for development and debugging.

    Format: "HH:MM:SS | LEVEL | logger.name | message"
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        datefmt='%H:%M:%S'
    )


def _preflight_env() -> None:
    """
    Preflight environment setup for GPU acceleration.

    This function ensures CUDA libraries are discoverable by the dynamic
    linker before any Python code imports them. On Linux, LD_LIBRARY_PATH
    must be set before process start, hence the re-exec pattern.

    The function:
    1. Checks if we've already run (sentinel variable)
    2. Locates NVIDIA CUDA libraries in the venv
    3. If found and not in LD_LIBRARY_PATH, re-execs with correct paths
    4. Sets CUDA_VISIBLE_DEVICES to ensure GPU is available

    Sentinel Pattern:
    -----------------
    `_VOCIFEROUS_ENV_READY` prevents infinite recursion. Without it:
    - Script runs, sets LD_LIBRARY_PATH, execs
    - New process runs, sets LD_LIBRARY_PATH, execs
    - ...forever
    """
    # Sentinel to prevent infinite re-exec loop
    if os.environ.get('_VOCIFEROUS_ENV_READY') == '1':
        return

    venv_path = Path(__file__).parent / '.venv'

    # Find Python version dynamically
    lib_path = venv_path / 'lib'
    if not lib_path.exists():
        return

    python_dirs = list(lib_path.glob('python3.*'))
    if not python_dirs:
        return

    site_packages = python_dirs[0] / 'site-packages' / 'nvidia'
    cudnn_lib = site_packages / 'cudnn' / 'lib'
    cublas_lib = site_packages / 'cublas' / 'lib'

    if cudnn_lib.exists() and cublas_lib.exists():
        ld_path = os.environ.get('LD_LIBRARY_PATH', '')
        cudnn_str, cublas_str = str(cudnn_lib), str(cublas_lib)

        if cudnn_str not in ld_path or cublas_str not in ld_path:
            # Re-exec with correct LD_LIBRARY_PATH (must be set before process starts)
            os.environ['LD_LIBRARY_PATH'] = f"{cudnn_str}:{cublas_str}:{ld_path}"
            os.environ['_VOCIFEROUS_ENV_READY'] = '1'
            os.execv(sys.executable, [sys.executable, *sys.argv])

    # Hint CUDA visibility
    os.environ.setdefault('CUDA_VISIBLE_DEVICES', '0')


# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

if __name__ == '__main__':
    _configure_logging()
    _preflight_env()

    # Suppress Qt Wayland warnings that can't be fixed (Wayland design limitation)
    os.environ['QT_LOGGING_RULES'] = 'qt.qpa.wayland=false'

    from main import VociferousApp
    app = VociferousApp()
    sys.exit(app.run())
