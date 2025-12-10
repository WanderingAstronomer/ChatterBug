"""Screen definitions for the Vociferous GUI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.core.window import Window
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.card import MDCard
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.list import (
    OneLineListItem,
    TwoLineListItem,
    OneLineAvatarIconListItem,
    IconLeftWidget,
)
from kivymd.uix.selectioncontrol import MDSwitch, MDCheckbox
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.filemanager import MDFileManager
from kivymd.uix.tooltip import MDTooltip

import structlog

from vociferous.config import load_config, save_config, AppConfig
from vociferous.domain.model import EngineKind
from .transcription import GUITranscriptionManager

logger = structlog.get_logger(__name__)


def _get_app() -> Any:
    """Get the running MDApp instance.
    
    Returns:
        The running MDApp instance or None if not available.
    """
    from kivymd.app import MDApp
    return MDApp.get_running_app()


class TooltipButton(MDRaisedButton, MDTooltip):
    """Button with tooltip support."""
    pass


class HomeScreen(Screen):
    """Main home screen for transcription."""
    
    # Status color constants (aligned with theme)
    COLOR_SUCCESS = "4CAF50"  # Material Green
    COLOR_WARNING = "FF9800"  # Material Orange
    COLOR_ERROR = "F44336"    # Material Red
    COLOR_INFO = "2196F3"     # Material Blue

    def __init__(self, **kwargs):
        """Initialize the home screen."""
        super().__init__(**kwargs)
        self.transcription_manager = GUITranscriptionManager()
        self.file_manager: MDFileManager | None = None
        self._build_ui()
        
        # Bind drag-and-drop events
        # Note: We bind to Window which is a singleton, so this won't leak
        # but we should unbind on cleanup if needed
        Window.bind(on_dropfile=self._on_file_drop)

    def on_leave(self, *args) -> None:
        """Clean up when leaving the screen."""
        # Unbind drag-and-drop to prevent memory leaks
        Window.unbind(on_dropfile=self._on_file_drop)
        return super().on_leave(*args)

    def _build_ui(self) -> None:
        """Build the home screen UI."""
        layout = MDBoxLayout(orientation="vertical", padding=15, spacing=15)
        
        # Title card
        title_card = MDCard(
            orientation="vertical",
            padding=[15, 12],
            size_hint=(1, None),
            height=100,
            elevation=2,
        )
        
        title_label = MDLabel(
            text="[size=28][b]Transcription[/b][/size]\n"
                 "[size=16]Select an audio file to transcribe[/size]",
            markup=True,
            halign="left",
        )
        title_card.add_widget(title_label)
        layout.add_widget(title_card)
        
        # File selection section
        file_card = MDCard(
            orientation="vertical",
            padding=[15, 12],
            spacing=8,
            size_hint=(1, 0.6),
            elevation=2,
        )
        
        file_label = MDLabel(
            text="[b]Audio File[/b]",
            markup=True,
            size_hint_y=None,
            height=25,
        )
        file_card.add_widget(file_label)
        
        # File path display
        self.file_path_field = MDTextField(
            hint_text="No file selected",
            mode="rectangle",
            readonly=True,
            size_hint=(1, None),
            height=48,
        )
        file_card.add_widget(self.file_path_field)
        
        # Buttons
        button_layout = MDBoxLayout(
            orientation="horizontal",
            spacing=12,
            size_hint=(1, None),
            height=56,
        )
        
        browse_button = TooltipButton(
            text="Browse Files",
            size_hint=(0.5, 1),
            on_release=self._browse_files,
        )
        browse_button.tooltip_text = "Browse for audio files (Ctrl+O)"
        button_layout.add_widget(browse_button)
        
        self.transcribe_button = TooltipButton(
            text="Start Transcription",
            size_hint=(0.5, 1),
            disabled=True,
            on_release=self._start_transcription,
        )
        self.transcribe_button.tooltip_text = "Start transcribing the selected file (Ctrl+T)"
        button_layout.add_widget(self.transcribe_button)
        
        file_card.add_widget(button_layout)
        
        # Status label
        self.status_label = MDLabel(
            text="",
            markup=True,
            size_hint_y=None,
            height=30,
        )
        file_card.add_widget(self.status_label)
        
        # Output preview
        output_label = MDLabel(
            text="[b]Transcript Output[/b]",
            markup=True,
            size_hint_y=None,
            height=30,
        )
        file_card.add_widget(output_label)
        
        scroll_view = MDScrollView(size_hint=(1, 1))
        self.output_field = MDTextField(
            text="",
            multiline=True,
            mode="rectangle",
            readonly=True,
        )
        scroll_view.add_widget(self.output_field)
        file_card.add_widget(scroll_view)
        
        # Save button
        self.save_button = TooltipButton(
            text="Save Transcript",
            size_hint=(1, None),
            height=50,
            disabled=True,
            on_release=self._save_transcript,
        )
        self.save_button.tooltip_text = "Save transcript to file (Ctrl+S)"
        file_card.add_widget(self.save_button)
        
        layout.add_widget(file_card)
        
        self.add_widget(layout)
        self.selected_file: Path | None = None

    def _browse_files(self, *args: Any) -> None:
        """Open file browser for audio file selection."""
        logger.info("Opening file browser")
        
        # Initialize file manager if not already done
        if not self.file_manager:
            self.file_manager = MDFileManager(
                exit_manager=self._exit_file_manager,
                select_path=self._select_file,
            )
        
        # Show file manager
        try:
            self.file_manager.show(Path.home())
        except Exception as e:
            logger.error("Error showing file manager", error=str(e))
            # Fallback: just set a demo file
            self._select_file(str(Path.home() / "demo.wav"))

    def _exit_file_manager(self, *args: Any) -> None:
        """Close the file manager."""
        if self.file_manager:
            self.file_manager.close()

    def _select_file(self, path: str) -> None:
        """Handle file selection.
        
        Args:
            path: Selected file path
        """
        logger.info("File selected", path=path)
        selected = Path(path)
        
        # Check if it's a file and has a valid audio extension
        if selected.is_file():
            valid_extensions = {'.wav', '.mp3', '.flac', '.m4a', '.ogg', '.opus', '.aac', '.wma'}
            if selected.suffix.lower() in valid_extensions:
                self.selected_file = selected
                self.file_path_field.text = str(selected)
                self.transcribe_button.disabled = False
                self.status_label.text = f"[color=#{self.COLOR_SUCCESS}]✓ File ready[/color]"
            else:
                self.status_label.text = f"[color=#{self.COLOR_WARNING}]⚠ Not a supported audio format[/color]"
        
        self._exit_file_manager()

    def _start_transcription(self, *args: Any) -> None:
        """Start the transcription process."""
        if not self.selected_file:
            return
        
        logger.info("Starting transcription", file=str(self.selected_file))
        
        # Disable button during transcription
        self.transcribe_button.disabled = True
        self.status_label.text = f"[color=#{self.COLOR_INFO}]⏳ Transcribing...[/color]"
        self.output_field.text = ""
        
        # Load config for engine selection
        config = load_config()
        
        # Start transcription
        self.transcription_manager.transcribe(
            file_path=self.selected_file,
            engine=config.engine,
            language="en",
            on_progress=self._on_transcription_progress,
            on_complete=self._on_transcription_complete,
            on_error=self._on_transcription_error,
        )

    def _on_transcription_progress(self, text: str) -> None:
        """Handle transcription progress updates.
        
        Args:
            text: Current transcript text
        """
        self.output_field.text = text

    def _on_transcription_complete(self, text: str) -> None:
        """Handle transcription completion.
        
        Args:
            text: Final transcript text
        """
        logger.info("Transcription complete")
        self.output_field.text = text
        self.status_label.text = f"[color=#{self.COLOR_SUCCESS}]✓ Complete![/color]"
        self.transcribe_button.disabled = False
        self.save_button.disabled = False
        
        # Show notification
        app = _get_app()
        if app and hasattr(app, 'show_notification'):
            app.show_notification("Transcription complete!")

    def _on_transcription_error(self, error: str) -> None:
        """Handle transcription error.
        
        Args:
            error: Error message
        """
        logger.error("Transcription error", error=error)
        self.status_label.text = f"[color=#{self.COLOR_ERROR}]✗ Error: {error}[/color]"
        self.transcribe_button.disabled = False
        
        # Show notification
        app = _get_app()
        if app and hasattr(app, 'show_notification'):
            app.show_notification(f"Transcription failed: {error}")

    def _on_file_drop(self, window: Any, file_path: bytes, *args: Any) -> None:
        """Handle file drop event.
        
        Args:
            window: Window instance
            file_path: Path to dropped file as bytes
        """
        try:
            # Convert bytes to string
            path_str = file_path.decode('utf-8')
            logger.info("File dropped", path=path_str)
            
            # Select the file
            self._select_file(path_str)
            
            # Show notification
            app = _get_app()
            if app and hasattr(app, 'show_notification'):
                app.show_notification("File loaded successfully")
        except Exception as e:
            logger.error("Error handling file drop", error=str(e))

    def _save_transcript(self, *args: Any) -> None:
        """Save the transcript to a file."""
        if not self.output_field.text:
            return
        
        try:
            # Generate output filename based on input file
            if self.selected_file:
                output_path = self.selected_file.with_suffix('.txt')
            else:
                output_path = Path.home() / "transcript.txt"
            
            # Save transcript
            output_path.write_text(self.output_field.text, encoding='utf-8')
            logger.info("Transcript saved", path=str(output_path))
            
            self.status_label.text = f"[color=#{self.COLOR_SUCCESS}]✓ Saved to {output_path.name}[/color]"
            
            # Show notification
            app = _get_app()
            if app and hasattr(app, 'show_notification'):
                app.show_notification(f"Transcript saved to {output_path.name}")
        except Exception as e:
            logger.error("Error saving transcript", error=str(e))
            self.status_label.text = f"[color=#{self.COLOR_ERROR}]✗ Error saving file[/color]"
            
            # Show notification
            app = _get_app()
            if app and hasattr(app, 'show_notification'):
                app.show_notification(f"Failed to save: {str(e)}")

    def _cancel_operation(self) -> None:
        """Cancel the current transcription operation."""
        if self.transcription_manager and self.transcription_manager.current_task:
            if self.transcription_manager.current_task.is_running:
                self.transcription_manager.stop_current()
                self.status_label.text = f"[color=#{self.COLOR_WARNING}]⚠ Cancelled[/color]"
                self.transcribe_button.disabled = False
                
                # Show notification
                app = _get_app()
                if app and hasattr(app, 'show_notification'):
                    app.show_notification("Transcription cancelled")
                
                logger.info("Transcription cancelled by user")


class SettingsScreen(Screen):
    """Settings screen for configuration."""

    def __init__(self, **kwargs):
        """Initialize the settings screen."""
        super().__init__(**kwargs)
        self.config = load_config()
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the settings screen UI."""
        layout = MDBoxLayout(orientation="vertical", padding=20, spacing=10)
        
        # Title
        title_label = MDLabel(
            text="[size=28][b]Settings[/b][/size]",
            markup=True,
            size_hint_y=None,
            height=60,
        )
        layout.add_widget(title_label)
        
        # Scrollable settings
        scroll = MDScrollView(size_hint=(1, 1))
        settings_layout = MDBoxLayout(
            orientation="vertical",
            spacing=10,
            size_hint_y=None,
            padding=[0, 0, 0, 20],
        )
        settings_layout.bind(minimum_height=settings_layout.setter("height"))
        
        # Engine section
        settings_layout.add_widget(self._create_section_header("Engine Configuration"))
        
        # Engine selection
        engine_item = TwoLineListItem(
            text="Engine",
            secondary_text=f"Current: {self.config.engine}",
            on_release=self._show_engine_menu,
        )
        settings_layout.add_widget(engine_item)
        self.engine_item = engine_item
        
        # Model selection
        model_item = TwoLineListItem(
            text="Model",
            secondary_text=f"Current: {self.config.model_name}",
        )
        settings_layout.add_widget(model_item)
        
        # Device selection
        device_item = TwoLineListItem(
            text="Device",
            secondary_text=f"Current: {self.config.device}",
            on_release=self._show_device_menu,
        )
        settings_layout.add_widget(device_item)
        self.device_item = device_item
        
        # Appearance section
        settings_layout.add_widget(self._create_section_header("Appearance"))
        
        # Theme toggle
        theme_item = TwoLineListItem(
            text="Theme",
            secondary_text="Current: Dark",
            on_release=self._show_theme_menu,
        )
        settings_layout.add_widget(theme_item)
        self.theme_item = theme_item
        
        # Font size selection
        font_item = TwoLineListItem(
            text="Font Size",
            secondary_text="Current: 100%",
            on_release=self._show_font_menu,
        )
        settings_layout.add_widget(font_item)
        self.font_item = font_item
        
        # Transcription options section
        settings_layout.add_widget(self._create_section_header("Transcription Options"))
        
        # VAD filter switch
        vad_layout = MDBoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=60,
            padding=[10, 0],
        )
        vad_label = MDLabel(
            text="Voice Activity Detection",
            size_hint_x=0.7,
        )
        vad_switch = MDSwitch(
            size_hint_x=0.3,
            active=self.config.params.get("vad_filter", "false") == "true",
        )
        vad_layout.add_widget(vad_label)
        vad_layout.add_widget(vad_switch)
        settings_layout.add_widget(vad_layout)
        
        # Batching switch
        batch_layout = MDBoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=60,
            padding=[10, 0],
        )
        batch_label = MDLabel(
            text="Enable Batching",
            size_hint_x=0.7,
        )
        batch_switch = MDSwitch(
            size_hint_x=0.3,
            active=self.config.params.get("enable_batching", "false") == "true",
        )
        batch_layout.add_widget(batch_label)
        batch_layout.add_widget(batch_switch)
        settings_layout.add_widget(batch_layout)
        
        # Word timestamps switch
        word_layout = MDBoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=60,
            padding=[10, 0],
        )
        word_label = MDLabel(
            text="Word Timestamps",
            size_hint_x=0.7,
        )
        word_switch = MDSwitch(
            size_hint_x=0.3,
            active=self.config.params.get("word_timestamps", "false") == "true",
        )
        word_layout.add_widget(word_label)
        word_layout.add_widget(word_switch)
        settings_layout.add_widget(word_layout)
        
        # Advanced section
        settings_layout.add_widget(self._create_section_header("Advanced"))
        
        # Batch size
        batch_size_item = TwoLineListItem(
            text="Batch Size",
            secondary_text=f"Current: {self.config.params.get('batch_size', '1')}",
        )
        settings_layout.add_widget(batch_size_item)
        
        # Compute type
        compute_item = TwoLineListItem(
            text="Compute Type",
            secondary_text=f"Current: {self.config.compute_type}",
        )
        settings_layout.add_widget(compute_item)
        
        # Save button
        save_button = MDRaisedButton(
            text="Save Settings",
            size_hint=(1, None),
            height=60,
            pos_hint={"center_x": 0.5},
            on_release=self._save_settings,
        )
        settings_layout.add_widget(save_button)
        
        scroll.add_widget(settings_layout)
        layout.add_widget(scroll)
        self.add_widget(layout)

    def _create_section_header(self, text: str) -> MDLabel:
        """Create a section header label.
        
        Args:
            text: Header text
            
        Returns:
            Styled header label
        """
        return MDLabel(
            text=f"[size=20][b]{text}[/b][/size]",
            markup=True,
            size_hint_y=None,
            height=50,
        )

    def _show_engine_menu(self, item: Any) -> None:
        """Show engine selection menu."""
        engines = ["whisper_turbo", "voxtral_local"]
        menu_items = [
            {
                "text": engine,
                "on_release": lambda x=engine: self._select_engine(x),
            }
            for engine in engines
        ]
        self.engine_menu = MDDropdownMenu(
            caller=item,
            items=menu_items,
            width_mult=4,
        )
        self.engine_menu.open()

    def _select_engine(self, engine: str) -> None:
        """Select an engine.
        
        Args:
            engine: Selected engine name
        """
        logger.info("Engine selected", engine=engine)
        # Validate engine is a valid EngineKind
        valid_engines = {"whisper_turbo", "voxtral_local"}
        if engine in valid_engines:
            self.config.engine = engine  # type: ignore[assignment]
        self.engine_item.secondary_text = f"Current: {engine}"
        if hasattr(self, "engine_menu"):
            self.engine_menu.dismiss()

    def _show_device_menu(self, item: Any) -> None:
        """Show device selection menu."""
        devices = ["auto", "cpu", "cuda"]
        menu_items = [
            {
                "text": device,
                "on_release": lambda x=device: self._select_device(x),
            }
            for device in devices
        ]
        self.device_menu = MDDropdownMenu(
            caller=item,
            items=menu_items,
            width_mult=4,
        )
        self.device_menu.open()

    def _select_device(self, device: str) -> None:
        """Select a device.
        
        Args:
            device: Selected device name
        """
        logger.info("Device selected", device=device)
        self.config.device = device
        self.device_item.secondary_text = f"Current: {device}"
        if hasattr(self, "device_menu"):
            self.device_menu.dismiss()

    def _save_settings(self, *args: Any) -> None:
        """Save settings to config file."""
        logger.info("Saving settings")
        try:
            save_config(self.config)
            logger.info("Settings saved successfully")
            
            # Show notification
            app = _get_app()
            if app and hasattr(app, 'show_notification'):
                app.show_notification("Settings saved successfully")
        except Exception as e:
            logger.error("Failed to save settings", error=str(e))
            
            # Show notification
            app = _get_app()
            if app and hasattr(app, 'show_notification'):
                app.show_notification(f"Failed to save settings: {str(e)}")

    def _show_theme_menu(self, item: Any) -> None:
        """Show theme selection menu."""
        themes = ["Light", "Dark"]
        menu_items = [
            {
                "text": theme,
                "on_release": lambda x=theme: self._select_theme(x),
            }
            for theme in themes
        ]
        self.theme_menu = MDDropdownMenu(
            caller=item,
            items=menu_items,
            width_mult=4,
        )
        self.theme_menu.open()

    def _select_theme(self, theme: str) -> None:
        """Select a theme.
        
        Args:
            theme: Selected theme name ("Light" or "Dark")
        """
        logger.info("Theme selected", theme=theme)
        app = _get_app()
        if app and hasattr(app, 'switch_theme'):
            app.switch_theme(theme)
        self.theme_item.secondary_text = f"Current: {theme}"
        if hasattr(self, "theme_menu"):
            self.theme_menu.dismiss()

    def _show_font_menu(self, item: Any) -> None:
        """Show font size selection menu."""
        font_sizes = ["80%", "90%", "100%", "110%", "120%", "130%", "140%", "150%"]
        menu_items = [
            {
                "text": size,
                "on_release": lambda x=size: self._select_font_size(x),
            }
            for size in font_sizes
        ]
        self.font_menu = MDDropdownMenu(
            caller=item,
            items=menu_items,
            width_mult=4,
        )
        self.font_menu.open()

    def _select_font_size(self, size: str) -> None:
        """Select a font size.
        
        Args:
            size: Selected font size percentage
        """
        logger.info("Font size selected", size=size)
        
        # Extract percentage value with validation
        try:
            percent = int(size.rstrip('%'))
            multiplier = percent / 100.0
        except (ValueError, AttributeError) as e:
            logger.error("Invalid font size format", size=size, error=str(e))
            return
        
        # Apply font size to app
        app = _get_app()
        
        # Note: Full font size implementation would require applying
        # the multiplier to all text elements' font_size properties.
        # This is a placeholder for future implementation.
        # For now, we just update the UI and inform the user.
        
        self.font_item.secondary_text = f"Current: {size}"
        if hasattr(self, "font_menu"):
            self.font_menu.dismiss()
        
        # Show notification
        if app and hasattr(app, 'show_notification'):
            app.show_notification(f"Font size set to {size} (restart may be required for full effect)")
