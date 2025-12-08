"""Targeted tests for WhisperTurboEngine CUDA library handling."""
from types import ModuleType
import ctypes
import os
import sys

from vociferous.engines.whisper_turbo import WhisperTurboEngine


def test_ensure_cuda_libs_updates_ld_library_path(monkeypatch, tmp_path):
    # Fake cudnn package with lib directory
    cudnn_root = tmp_path / "cudnn"
    lib_dir = cudnn_root / "lib"
    lib_dir.mkdir(parents=True)
    (lib_dir / "libcudnn_ops.so.9").write_text("", encoding="utf-8")

    nvidia_mod = ModuleType("nvidia")
    cudnn_mod = ModuleType("nvidia.cudnn")
    cudnn_mod.__path__ = [str(cudnn_root)]
    nvidia_mod.cudnn = cudnn_mod
    sys.modules["nvidia"] = nvidia_mod
    sys.modules["nvidia.cudnn"] = cudnn_mod

    # Fake ctranslate2 package with bundled libs
    ct_lib_dir = tmp_path / "ctranslate2.libs"
    ct_lib_dir.mkdir(parents=True)
    ct_mod = ModuleType("ctranslate2")
    ct_mod.__file__ = str((tmp_path / "ctranslate2_pkg" / "__init__.py"))
    sys.modules["ctranslate2"] = ct_mod

    monkeypatch.setenv("LD_LIBRARY_PATH", "")
    monkeypatch.setattr(ctypes, "CDLL", lambda path: path)

    engine = object.__new__(WhisperTurboEngine)
    WhisperTurboEngine._ensure_cuda_libs(engine)

    env_value = os.environ.get("LD_LIBRARY_PATH", "")

    assert str(lib_dir) in env_value
    assert str(ct_lib_dir) in env_value
