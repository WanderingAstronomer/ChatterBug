"""Dependency installer for GPU/CPU configurations."""

from __future__ import annotations

import subprocess
import sys
from enum import Enum
from typing import List

import structlog

logger = structlog.get_logger(__name__)


class InstallMode(str, Enum):
    """Installation mode for dependencies."""
    GPU = "gpu"
    CPU = "cpu"
    BOTH = "both"


class DependencyInstaller:
    """Handles installation of GPU/CPU-specific dependencies."""

    def __init__(self) -> None:
        """Initialize the dependency installer."""
        self.pip_executable = sys.executable

    def install_gpu_dependencies(self) -> bool:
        """Install GPU-specific dependencies.
        
        Returns:
            True if installation successful, False otherwise.
        """
        logger.info("Installing GPU dependencies...")
        gpu_deps = [
            "torch>=2.0.0",
            "nvidia-cudnn-cu12>=9.1.0.70",
        ]
        return self._install_packages(gpu_deps)

    def install_cpu_dependencies(self) -> bool:
        """Install CPU-specific dependencies.
        
        Returns:
            True if installation successful, False otherwise.
        """
        logger.info("Installing CPU dependencies...")
        # For CPU, we install PyTorch with CPU-only support
        cpu_deps = [
            "torch>=2.0.0",  # Will use CPU by default if no CUDA
        ]
        return self._install_packages(cpu_deps)

    def install_dependencies(self, mode: InstallMode) -> bool:
        """Install dependencies based on selected mode.
        
        Args:
            mode: Installation mode (GPU, CPU, or BOTH)
            
        Returns:
            True if installation successful, False otherwise.
        """
        if mode == InstallMode.GPU:
            return self.install_gpu_dependencies()
        elif mode == InstallMode.CPU:
            return self.install_cpu_dependencies()
        elif mode == InstallMode.BOTH:
            # For "both", install GPU deps which work on CPU too
            return self.install_gpu_dependencies()
        return False

    def _install_packages(self, packages: List[str]) -> bool:
        """Install a list of packages using pip.
        
        Args:
            packages: List of package specifications
            
        Returns:
            True if all packages installed successfully, False otherwise.
        """
        try:
            cmd = [self.pip_executable, "-m", "pip", "install"] + packages
            logger.info("Running pip install", command=" ".join(cmd))
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            logger.info("Installation successful", stdout=result.stdout)
            return True
        except subprocess.CalledProcessError as e:
            logger.error("Installation failed", stderr=e.stderr, returncode=e.returncode)
            return False
        except Exception as e:
            logger.error("Unexpected error during installation", error=str(e))
            return False

    def check_installation_status(self) -> dict[str, bool]:
        """Check which dependencies are currently installed.
        
        Returns:
            Dictionary with installation status for each dependency type.
        """
        status = {
            "torch": False,
            "cuda": False,
        }
        
        try:
            import torch
            status["torch"] = True
            status["cuda"] = torch.cuda.is_available()
        except ImportError:
            pass
        
        return status
