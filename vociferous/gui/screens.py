"""Screen definitions for the Luciferous GUI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.filechooser import FileChooserListView
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

import structlog

from vociferous.config import load_config, AppConfig
from vociferous.domain.model import EngineKind

logger = structlog.get_logger(__name__)


class HomeScreen(Screen):
    """Main home screen for transcription."""

    def __init__(self, **kwargs):
        """Initialize the home screen."""
        super().__init__(**kwargs)
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the home screen UI."""
        layout = MDBoxLayout(orientation="vertical", padding=20, spacing=20)
        
        # Title card
        title_card = MDCard(
            orientation="vertical",
            padding=20,
            size_hint=(1, None),
            height=150,
            elevation=5,
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
            padding=20,
            spacing=15,
            size_hint=(1, 0.6),
            elevation=5,
        )
        
        file_label = MDLabel(
            text="[b]Audio File[/b]",
            markup=True,
            size_hint_y=None,
            height=30,
        )
        file_card.add_widget(file_label)
        
        # File path display
        self.file_path_field = MDTextField(
            hint_text="No file selected",
            mode="rectangle",
            readonly=True,
            size_hint=(1, None),
            height=50,
        )
        file_card.add_widget(self.file_path_field)
        
        # Buttons
        button_layout = MDBoxLayout(
            orientation="horizontal",
            spacing=15,
            size_hint=(1, None),
            height=60,
        )
        
        browse_button = MDRaisedButton(
            text="Browse Files",
            size_hint=(0.5, 1),
            md_bg_color=(0.2, 0.4, 0.8, 1),
            on_release=self._browse_files,
        )
        button_layout.add_widget(browse_button)
        
        self.transcribe_button = MDRaisedButton(
            text="Start Transcription",
            size_hint=(0.5, 1),
            md_bg_color=(0.1, 0.6, 0.3, 1),
            disabled=True,
            on_release=self._start_transcription,
        )
        button_layout.add_widget(self.transcribe_button)
        
        file_card.add_widget(button_layout)
        
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
        
        layout.add_widget(file_card)
        
        self.add_widget(layout)
        self.selected_file: Path | None = None

    def _browse_files(self, *args: Any) -> None:
        """Open file browser for audio file selection."""
        logger.info("Browse files clicked")
        # In a real implementation, would open a file dialog
        # For now, just set a placeholder
        self.file_path_field.text = "/path/to/audio/file.wav"
        self.selected_file = Path("/path/to/audio/file.wav")
        self.transcribe_button.disabled = False

    def _start_transcription(self, *args: Any) -> None:
        """Start the transcription process."""
        if not self.selected_file:
            return
        
        logger.info("Starting transcription", file=str(self.selected_file))
        self.output_field.text = "Transcription in progress...\n\n"
        # In a real implementation, would call TranscriptionSession
        # For demonstration:
        self.output_field.text += "This is where the transcript would appear."


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
            active=self.config.params.get("vad_filter", "true") == "true",
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
            md_bg_color=(0.1, 0.6, 0.3, 1),
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
            text=f"[size=20][b][color=#4A9EFF]{text}[/color][/b][/size]",
            markup=True,
            size_hint_y=None,
            height=50,
        )

    def _show_engine_menu(self, item: Any) -> None:
        """Show engine selection menu."""
        engines = ["whisper_turbo", "voxtral_local", "whisper_vllm", "voxtral_vllm"]
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
        self.config.engine = engine  # type: ignore
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
        # In a real implementation, would save to config file
        # For now, just log
        logger.info("Settings saved", config=self.config)
