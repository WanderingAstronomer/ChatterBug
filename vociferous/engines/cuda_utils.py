"""CUDA library path management for GPU inference."""

from __future__ import annotations

import ctypes
import logging
import os
from collections.abc import Iterable
from pathlib import Path

logger = logging.getLogger(__name__)


def _existing_lib_dirs(packages: Iterable[object]) -> list[str]:
    lib_dirs: list[str] = []
    for pkg in packages:
        for pkg_path in getattr(pkg, "__path__", []):
            lib_dir = Path(pkg_path) / "lib"
            if lib_dir.exists():
                lib_dirs.append(str(lib_dir))
    return lib_dirs


def ensure_cuda_libs_available() -> bool:
    """Ensure CUDA-related libs provided by wheels are discoverable.

    Returns:
        True if any CUDA libs were found/configured; False otherwise.
    """
    try:
        import nvidia.cudnn  # type: ignore
    except ImportError:
        return False

    lib_dirs: list[str] = []
    lib_dirs.extend(_existing_lib_dirs((nvidia.cudnn,)))

    try:
        import ctranslate2  # type: ignore
    except ImportError:
        ctranslate2 = None

    if ctranslate2:
        ct_file = getattr(ctranslate2, "__file__", None)
        if ct_file:
            ct_lib_dir = (Path(ct_file).resolve().parent.parent / "ctranslate2.libs").resolve()
            if ct_lib_dir.exists():
                lib_dirs.append(str(ct_lib_dir))

    if not lib_dirs:
        return False

    existing = os.environ.get("LD_LIBRARY_PATH", "")
    extras = ":".join(lib_dirs)
    if extras not in existing:
        os.environ["LD_LIBRARY_PATH"] = f"{extras}:{existing}" if existing else extras

    candidates: list[Path] = []
    for lib_dir in lib_dirs:
        base = Path(lib_dir)
        for name in (
            "libcudnn_cnn.so.9.1.0",
            "libcudnn_cnn.so.9.1",
            "libcudnn_cnn.so.9",
            "libcudnn_cnn.so",
            "libcudnn_ops.so.9.1.0",
            "libcudnn_ops.so.9.1",
            "libcudnn_ops.so.9",
            "libcudnn_ops.so",
        ):
            cand = base / name
            if cand.exists():
                candidates.append(cand)

    for cand in candidates:
        try:
            ctypes.CDLL(str(cand))
            return True
        except OSError as exc:
            logger.warning("Failed to preload CUDA lib %s: %s", cand, exc)

    return True
