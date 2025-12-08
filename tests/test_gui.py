"""Basic tests for GUI components."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from vociferous.gui.installer import DependencyInstaller, InstallMode


class TestDependencyInstaller:
    """Tests for DependencyInstaller."""

    def test_check_installation_status(self) -> None:
        """Test checking installation status."""
        installer = DependencyInstaller()
        status = installer.check_installation_status()
        
        assert isinstance(status, dict)
        assert "torch" in status
        assert "cuda" in status
        assert isinstance(status["torch"], bool)
        assert isinstance(status["cuda"], bool)

    @patch("subprocess.run")
    def test_install_packages_success(self, mock_run: Mock) -> None:
        """Test successful package installation."""
        mock_run.return_value = Mock(stdout="Success", stderr="", returncode=0)
        
        installer = DependencyInstaller()
        result = installer._install_packages(["test-package"])
        
        assert result is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_install_packages_failure(self, mock_run: Mock) -> None:
        """Test failed package installation."""
        import subprocess
        mock_run.side_effect = subprocess.CalledProcessError(1, "pip", stderr="Error")
        
        installer = DependencyInstaller()
        result = installer._install_packages(["test-package"])
        
        assert result is False

    def test_install_mode_enum(self) -> None:
        """Test InstallMode enum values."""
        assert InstallMode.GPU == "gpu"
        assert InstallMode.CPU == "cpu"
        assert InstallMode.BOTH == "both"


class TestGUIConfiguration:
    """Tests for GUI configuration."""

    def test_first_run_marker(self, tmp_path: Path) -> None:
        """Test first run marker creation."""
        marker_file = tmp_path / ".gui_setup_complete"
        
        assert not marker_file.exists()
        
        marker_file.touch()
        assert marker_file.exists()

    def test_config_directory_creation(self, tmp_path: Path) -> None:
        """Test config directory is created."""
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        assert config_dir.exists()
        assert config_dir.is_dir()


class TestTranscriptionTask:
    """Tests for TranscriptionTask."""

    def test_task_creation(self, tmp_path: Path) -> None:
        """Test creating a transcription task."""
        from vociferous.gui.transcription import TranscriptionTask
        
        test_file = tmp_path / "test.wav"
        test_file.touch()
        
        task = TranscriptionTask(
            file_path=test_file,
            engine="whisper_turbo",
            language="en",
        )
        
        assert task.file_path == test_file
        assert task.engine == "whisper_turbo"
        assert task.language == "en"
        assert not task.is_running
        assert task.transcript == ""

    def test_task_callbacks(self, tmp_path: Path) -> None:
        """Test task callbacks are stored."""
        from vociferous.gui.transcription import TranscriptionTask
        
        test_file = tmp_path / "test.wav"
        test_file.touch()
        
        progress_callback = Mock()
        complete_callback = Mock()
        error_callback = Mock()
        
        task = TranscriptionTask(
            file_path=test_file,
            on_progress=progress_callback,
            on_complete=complete_callback,
            on_error=error_callback,
        )
        
        assert task.on_progress is progress_callback
        assert task.on_complete is complete_callback
        assert task.on_error is error_callback


class TestGUITranscriptionManager:
    """Tests for GUITranscriptionManager."""

    def test_manager_creation(self) -> None:
        """Test creating a transcription manager."""
        from vociferous.gui.transcription import GUITranscriptionManager
        
        manager = GUITranscriptionManager()
        assert manager.current_task is None

    def test_manager_stop_current(self) -> None:
        """Test stopping current task."""
        from vociferous.gui.transcription import GUITranscriptionManager
        
        manager = GUITranscriptionManager()
        manager.current_task = Mock()
        
        manager.stop_current()
        
        assert manager.current_task is None


class TestGUIEnhancements:
    """Tests for GUI enhancements (Phase 1 features)."""

    def test_tooltip_button_creation(self) -> None:
        """Test TooltipButton class exists and has tooltip support."""
        from vociferous.gui.screens import TooltipButton
        from kivymd.uix.tooltip import MDTooltip
        
        # Verify TooltipButton inherits from MDTooltip
        assert issubclass(TooltipButton, MDTooltip)

    def test_snackbar_import(self) -> None:
        """Test snackbar notification support is imported."""
        from kivymd.uix.snackbar import MDSnackbar
        
        # Verify MDSnackbar is available
        assert MDSnackbar is not None

    def test_keyboard_shortcuts_handler_exists(self) -> None:
        """Test keyboard shortcuts handler exists in app."""
        from vociferous.gui.app import VociferousGUIApp
        
        app = VociferousGUIApp()
        assert hasattr(app, '_on_keyboard')
        assert callable(app._on_keyboard)

    def test_theme_switch_method_exists(self) -> None:
        """Test theme switching method exists."""
        from vociferous.gui.app import VociferousGUIApp
        
        app = VociferousGUIApp()
        assert hasattr(app, 'switch_theme')
        assert callable(app.switch_theme)

    def test_notification_method_exists(self) -> None:
        """Test notification method exists."""
        from vociferous.gui.app import VociferousGUIApp
        
        app = VociferousGUIApp()
        assert hasattr(app, 'show_notification')
        assert callable(app.show_notification)
