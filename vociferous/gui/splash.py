"""Splash screen for first-run setup and dependency installation."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.progressbar import MDProgressBar

import structlog

from .installer import DependencyInstaller, InstallMode

logger = structlog.get_logger(__name__)


class SplashScreen(Screen):
    """First-run splash screen with dependency selection."""
    
    # Status color constants (aligned with Material Design)
    COLOR_SUCCESS = "4CAF50"  # Material Green
    COLOR_ERROR = "F44336"    # Material Red

    def __init__(self, on_complete: Callable[[InstallMode | None], None], **kwargs):
        """Initialize the splash screen.
        
        Args:
            on_complete: Callback when setup is complete, receives selected InstallMode
            **kwargs: Additional screen arguments
        """
        super().__init__(name="splash", **kwargs)
        self.on_complete = on_complete
        self.installer = DependencyInstaller()
        self.selected_mode: InstallMode | None = None
        
        # Check if this is first run
        self.is_first_run = self._check_first_run()
        
        # Build UI
        self._build_ui()

    def _check_first_run(self) -> bool:
        """Check if this is the first run of the application.
        
        Returns:
            True if first run, False otherwise.
        """
        marker_file = Path.home() / ".config" / "vociferous" / ".gui_setup_complete"
        return not marker_file.exists()

    def _mark_setup_complete(self) -> None:
        """Mark the setup as complete."""
        marker_file = Path.home() / ".config" / "vociferous" / ".gui_setup_complete"
        marker_file.parent.mkdir(parents=True, exist_ok=True)
        marker_file.touch()

    def _build_ui(self) -> None:
        """Build the splash screen UI."""
        layout = BoxLayout(orientation="vertical", padding=40, spacing=20)
        
        # Welcome card
        card = MDCard(
            orientation="vertical",
            padding=30,
            spacing=20,
            size_hint=(0.8, None),
            height=500,
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            elevation=5,
        )
        
        # Welcome message
        welcome_label = MDLabel(
            text="[size=32][b]Welcome to Vociferous![/b][/size]\n\n"
                 "[size=18]Your AI-powered transcription assistant[/size]",
            markup=True,
            halign="center",
            size_hint_y=None,
            height=120,
        )
        card.add_widget(welcome_label)
        
        if self.is_first_run:
            # First run: show installation options
            setup_label = MDLabel(
                text="[size=16]To get started, please select your hardware configuration:[/size]",
                markup=True,
                halign="center",
                size_hint_y=None,
                height=50,
            )
            card.add_widget(setup_label)
            
            # Installation buttons
            button_layout = BoxLayout(
                orientation="vertical",
                spacing=10,
                size_hint_y=None,
                height=200,
                padding=[40, 0],
            )
            
            gpu_button = MDRaisedButton(
                text="GPU (NVIDIA CUDA)",
                size_hint=(1, None),
                height=60,
                on_release=lambda x: self._on_mode_selected(InstallMode.GPU)
            )
            button_layout.add_widget(gpu_button)
            
            cpu_button = MDRaisedButton(
                text="CPU Only",
                size_hint=(1, None),
                height=60,
                on_release=lambda x: self._on_mode_selected(InstallMode.CPU)
            )
            button_layout.add_widget(cpu_button)
            
            both_button = MDRaisedButton(
                text="Both (Flexible)",
                size_hint=(1, None),
                height=60,
                on_release=lambda x: self._on_mode_selected(InstallMode.BOTH)
            )
            button_layout.add_widget(both_button)
            
            card.add_widget(button_layout)
            
            # Progress bar (hidden initially)
            self.progress_bar = MDProgressBar(
                size_hint=(1, None),
                height=10,
                opacity=0,
            )
            card.add_widget(self.progress_bar)
            
            # Status label
            self.status_label = MDLabel(
                text="",
                markup=True,
                halign="center",
                size_hint_y=None,
                height=40,
            )
            card.add_widget(self.status_label)
            
        else:
            # Not first run: just show continue button
            continue_label = MDLabel(
                text="[size=16]Ready to transcribe![/size]",
                markup=True,
                halign="center",
                size_hint_y=None,
                height=50,
            )
            card.add_widget(continue_label)
            
            continue_button = MDRaisedButton(
                text="Continue",
                size_hint=(None, None),
                size=(200, 60),
                pos_hint={"center_x": 0.5},
                on_release=lambda x: self._skip_setup()
            )
            card.add_widget(continue_button)
        
        layout.add_widget(card)
        self.add_widget(layout)

    def _on_mode_selected(self, mode: InstallMode) -> None:
        """Handle installation mode selection.
        
        Args:
            mode: Selected installation mode
        """
        logger.info("Installation mode selected", mode=mode.value)
        self.selected_mode = mode
        
        # Show progress
        self.progress_bar.opacity = 1
        self.status_label.text = f"[size=14]Installing {mode.value.upper()} dependencies...[/size]"
        
        # Start installation in background thread
        from kivy.clock import Clock
        import threading
        
        def install_thread():
            """Run installation in background."""
            success = self.installer.install_dependencies(mode)
            # Schedule UI update on main thread
            Clock.schedule_once(lambda dt: self._on_installation_complete(success), 0)
        
        thread = threading.Thread(target=install_thread, daemon=True)
        thread.start()

    def _on_installation_complete(self, success: bool) -> None:
        """Handle installation completion (called on main thread).
        
        Args:
            success: Whether installation succeeded
        """
        if success:
            self.status_label.text = f"[size=14][color=#{self.COLOR_SUCCESS}]Installation complete![/color][/size]"
            self._mark_setup_complete()
            # Delay before continuing
            from kivy.clock import Clock
            Clock.schedule_once(lambda dt: self._complete_setup(), 1.5)
        else:
            self.status_label.text = f"[size=14][color=#{self.COLOR_ERROR}]Installation failed. Please try again.[/color][/size]"
            self.progress_bar.opacity = 0

    def _skip_setup(self) -> None:
        """Skip setup (not first run)."""
        self._complete_setup()

    def _complete_setup(self) -> None:
        """Complete the setup process."""
        logger.info("Splash screen complete", mode=self.selected_mode)
        self.on_complete(self.selected_mode)
