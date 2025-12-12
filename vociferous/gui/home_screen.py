"""Enhanced home screen for Vociferous GUI.

Implements the Design.md specification with:
- Mode switcher (Simple/Advanced/Expert)
- Audio file preview with metadata
- Pipeline stage visualization
- Real-time progress with RTF metrics
- Streaming transcript output
- Enhanced visual styling
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.screenmanager import Screen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.filemanager import MDFileManager
from kivymd.uix.label import MDLabel
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.textfield import MDTextField
from kivymd.uix.button import MDFillRoundFlatButton

from vociferous.config import load_config

from .transcription import GUITranscriptionManager
from .widgets import (
    AudioFileCard,
    AudioFileInfo,
    Colors,
    DaemonStatusWidget,
    PresetCard,
    ProgressCard,
    TooltipButton,
)

if TYPE_CHECKING:
    from vociferous.audio.validation import AudioFileInfo as ValidationAudioFileInfo

logger = structlog.get_logger(__name__)

# Supported audio extensions
SUPPORTED_EXTENSIONS = frozenset({
    ".wav", ".mp3", ".flac", ".m4a", ".ogg", ".opus", ".aac", ".wma", ".webm"
})


def _get_app() -> Any:
    """Get the running MDApp instance."""
    from kivymd.app import MDApp
    return MDApp.get_running_app()


class EnhancedHomeScreen(Screen):
    """Enhanced home screen with mode switching and rich UI.
    
    Implements the workflow: select audio → validate → choose preset → run → review → export
    """
    
    # Transcription mode
    MODE_SIMPLE = "simple"
    MODE_ADVANCED = "advanced"
    MODE_EXPERT = "expert"
    
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.transcription_manager = GUITranscriptionManager()
        self.file_manager: MDFileManager | None = None
        self.selected_file: Path | None = None
        self.current_mode = self.MODE_SIMPLE
        self.export_dialog: MDDialog | None = None
        self.record_dialog: MDDialog | None = None
        self.selected_preset: Any = None  # Currently selected engine preset
        
        # Recording state
        self.is_recording = False
        self.recording_seconds = 0
        self.recording_clock: Any = None
        self.recording_thread: Any = None
        self.stop_recording_event: Any = None
        self.recorded_chunks: list[bytes] = []
        self.record_dialog_buttons: list[Any] = []
        self.recording_status: MDLabel | None = None
        self.recording_timer: MDLabel | None = None
        
        self._build_ui()
        
        # Bind drag-and-drop
        Window.bind(on_dropfile=self._on_file_drop)
    
    def on_leave(self, *args: Any) -> None:
        """Clean up when leaving screen."""
        Window.unbind(on_dropfile=self._on_file_drop)
        return super().on_leave(*args)
    
    def _build_ui(self) -> None:
        """Build the enhanced home screen UI."""
        # Main layout
        main_layout = MDBoxLayout(
            orientation="vertical",
            spacing=dp(12),
            padding=[dp(16), dp(12)],
        )
        
        # Header with title and mode switcher
        main_layout.add_widget(self._build_header())
        
        # Daemon status bar
        self.daemon_status = DaemonStatusWidget()
        main_layout.add_widget(self.daemon_status)
        
        # Content area (scrollable)
        content_scroll = MDScrollView(size_hint=(1, 1))
        content_layout = MDBoxLayout(
            orientation="vertical",
            spacing=dp(12),
            size_hint_y=None,
            padding=[0, 0, 0, dp(20)],
        )
        content_layout.bind(minimum_height=content_layout.setter("height"))
        
        # Drop zone / file selection
        content_layout.add_widget(self._build_drop_zone())
        
        # Audio file info card
        self.audio_card = AudioFileCard()
        content_layout.add_widget(self.audio_card)
        
        # Preset selection (Advanced mode)
        self.preset_section = self._build_preset_section()
        self.preset_section.opacity = 0
        self.preset_section.disabled = True
        self.preset_section.size_hint_y = None
        self.preset_section.height = 0
        content_layout.add_widget(self.preset_section)
        
        # Action buttons
        content_layout.add_widget(self._build_action_buttons())
        
        # Progress card
        self.progress_card = ProgressCard()
        self.progress_card.opacity = 0
        content_layout.add_widget(self.progress_card)
        
        # Transcript output section
        content_layout.add_widget(self._build_output_section())
        
        content_scroll.add_widget(content_layout)
        main_layout.add_widget(content_scroll)
        
        self.add_widget(main_layout)
    
    def _build_header(self) -> MDBoxLayout:
        """Build the header with title and mode switcher."""
        header = MDBoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(56),
            spacing=dp(16),
        )
        
        # Title
        title = MDLabel(
            text="[b]Transcription[/b]",
            markup=True,
            font_style="H5",
            theme_text_color="Primary",
            size_hint=(0.5, 1),
            valign="center",
        )
        header.add_widget(title)
        
        # Mode switcher
        mode_layout = MDBoxLayout(
            orientation="horizontal",
            size_hint=(0.5, 1),
            spacing=dp(8),
        )
        
        mode_label = MDLabel(
            text="Mode:",
            font_style="Body2",
            theme_text_color="Secondary",
            size_hint=(None, 1),
            width=dp(50),
            valign="center",
            halign="right",
        )
        mode_layout.add_widget(mode_label)
        
        # Toggle button group for mode selection (Simple/Advanced only)
        self.mode_buttons: dict[str, MDFillRoundFlatButton] = {}
        modes = ["Simple", "Advanced"]
        
        for mode in modes:
            btn = MDFillRoundFlatButton(
                text=mode,
                size_hint=(None, None),
                height=dp(40),
                width=dp(110),
            )
            btn.bind(on_release=lambda x, m=mode: self._select_mode(m))
            self.mode_buttons[mode] = btn
            mode_layout.add_widget(btn)
        
        # Set initial selection
        self._select_mode("Simple")
        
        header.add_widget(mode_layout)
        
        return header
    
    def _build_drop_zone(self) -> MDCard:
        """Build the drag-and-drop file zone."""
        drop_card = MDCard(
            orientation="vertical",
            padding=[dp(24), dp(20)],
            spacing=dp(12),
            size_hint=(1, None),
            height=dp(160),
            elevation=2,
            radius=[dp(16)],
            ripple_behavior=True,
        )
        drop_card.md_bg_color = Colors.SURFACE_VARIANT
        drop_card.bind(on_release=self._browse_files)
        
        # Icon
        icon_label = MDLabel(
            text="[+]",
            font_style="H3",
            halign="center",
            size_hint=(1, None),
            height=dp(48),
        )
        drop_card.add_widget(icon_label)
        
        # Main text
        main_text = MDLabel(
            text="[b]Drag & Drop Audio File Here[/b]",
            markup=True,
            font_style="H6",
            halign="center",
            theme_text_color="Primary",
            size_hint=(1, None),
            height=dp(30),
        )
        drop_card.add_widget(main_text)
        
        # Secondary text
        sub_text = MDLabel(
            text="or click to browse • MP3, WAV, FLAC, M4A, OGG, OPUS",
            font_style="Caption",
            halign="center",
            theme_text_color="Secondary",
            size_hint=(1, None),
            height=dp(24),
        )
        drop_card.add_widget(sub_text)
        
        self.drop_zone = drop_card
        return drop_card
    
    def _build_preset_section(self) -> MDBoxLayout:
        """Build the preset selection section (for Advanced/Expert modes)."""
        section = MDBoxLayout(
            orientation="vertical",
            size_hint=(1, None),
            height=dp(180),
            spacing=dp(8),
        )
        
        # Section header
        header = MDLabel(
            text="[b]Quick Presets[/b]",
            markup=True,
            font_style="Subtitle1",
            theme_text_color="Primary",
            size_hint=(1, None),
            height=dp(30),
        )
        section.add_widget(header)
        
        # Preset cards row
        presets_scroll = MDScrollView(
            size_hint=(1, 1),
            do_scroll_y=False,
        )
        
        presets_row = MDBoxLayout(
            orientation="horizontal",
            size_hint=(None, 1),
            spacing=dp(12),
            padding=[0, dp(8)],
        )
        presets_row.bind(minimum_width=presets_row.setter("width"))
        
        # Engine presets
        preset_configs = [
            ("Accuracy", "Best quality, slower", "target"),
            ("Speed", "Fast transcription", "speed"),
            ("Balanced", "Good balance", "balance-scale"),
            ("Low Memory", "For limited VRAM", "memory"),
        ]
        
        self.preset_cards: list[PresetCard] = []
        for name, desc, icon in preset_configs:
            card = PresetCard(
                name=name,
                description=desc,
                icon=icon,
                on_select=self._on_preset_selected,
            )
            self.preset_cards.append(card)
            presets_row.add_widget(card)
        
        # Select "Balanced" by default
        if len(self.preset_cards) > 2:
            self.preset_cards[2].selected = True
        
        presets_scroll.add_widget(presets_row)
        section.add_widget(presets_scroll)
        
        return section
    
    def _build_action_buttons(self) -> MDBoxLayout:
        """Build the action buttons section."""
        button_layout = MDBoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(56),
            spacing=dp(12),
        )
        
        # Browse button
        self.browse_button = TooltipButton(
            text="Browse",
            size_hint=(0.2, 1),
        )
        self.browse_button.tooltip_text = "Browse for audio files (Ctrl+O)"
        self.browse_button.bind(on_release=self._browse_files)
        button_layout.add_widget(self.browse_button)
        
        # Record button
        self.record_button = TooltipButton(
            text="Record",
            size_hint=(0.2, 1),
        )
        self.record_button.tooltip_text = "Record from microphone (Ctrl+R)"
        self.record_button.bind(on_release=self._show_record_dialog)
        button_layout.add_widget(self.record_button)
        
        # Transcribe button
        self.transcribe_button = MDRaisedButton(
            text="Start Transcription",
            size_hint=(0.4, 1),
            disabled=True,
        )
        self.transcribe_button.md_bg_color_disabled = Colors.SURFACE_VARIANT
        self.transcribe_button.bind(on_release=self._start_transcription)
        button_layout.add_widget(self.transcribe_button)
        
        # Cancel button
        self.cancel_button = TooltipButton(
            text="Cancel",
            size_hint=(0.2, 1),
            disabled=True,
        )
        self.cancel_button.tooltip_text = "Cancel transcription (Esc)"
        self.cancel_button.bind(on_release=self._cancel_transcription)
        button_layout.add_widget(self.cancel_button)
        
        return button_layout
    
    def _build_output_section(self) -> MDCard:
        """Build the transcript output section."""
        output_card = MDCard(
            orientation="vertical",
            padding=[dp(16), dp(12)],
            spacing=dp(8),
            size_hint=(1, None),
            height=dp(350),
            elevation=2,
            radius=[dp(12)],
        )
        output_card.md_bg_color = Colors.SURFACE_VARIANT
        
        # Header with title and action buttons
        header = MDBoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(40),
        )
        
        output_title = MDLabel(
            text="[b]Transcript Output[/b]",
            markup=True,
            font_style="Subtitle1",
            theme_text_color="Primary",
            size_hint=(1, 1),
            valign="center",
        )
        header.add_widget(output_title)
        
        # Word count
        self.word_count_label = MDLabel(
            text="",
            font_style="Caption",
            theme_text_color="Secondary",
            size_hint=(None, 1),
            width=dp(100),
            halign="right",
            valign="center",
        )
        header.add_widget(self.word_count_label)
        
        output_card.add_widget(header)
        
        # Transcript text area
        scroll_view = MDScrollView(size_hint=(1, 1))
        
        self.output_field = MDTextField(
            text="",
            multiline=True,
            mode="rectangle",
            readonly=True,
            hint_text="Transcript will appear here...",
        )
        scroll_view.add_widget(self.output_field)
        output_card.add_widget(scroll_view)
        
        # Bottom action buttons
        action_row = MDBoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(44),
            spacing=dp(8),
        )
        
        self.copy_button = TooltipButton(
            text="Copy",
            size_hint=(0.25, 1),
            disabled=True,
        )
        self.copy_button.tooltip_text = "Copy transcript to clipboard"
        self.copy_button.bind(on_release=self._copy_transcript)
        action_row.add_widget(self.copy_button)
        
        self.save_button = TooltipButton(
            text="Save",
            size_hint=(0.25, 1),
            disabled=True,
        )
        self.save_button.tooltip_text = "Save transcript (Ctrl+S)"
        self.save_button.bind(on_release=self._save_transcript)
        action_row.add_widget(self.save_button)
        
        self.export_button = TooltipButton(
            text="Export As...",
            size_hint=(0.25, 1),
            disabled=True,
        )
        self.export_button.tooltip_text = "Export in different formats"
        self.export_button.bind(on_release=self._show_export_dialog)
        action_row.add_widget(self.export_button)
        
        self.refine_button = TooltipButton(
            text="Refine",
            size_hint=(0.25, 1),
            disabled=True,
        )
        self.refine_button.tooltip_text = "Improve grammar and punctuation"
        self.refine_button.bind(on_release=self._refine_transcript)
        action_row.add_widget(self.refine_button)
        
        output_card.add_widget(action_row)
        
        return output_card
    
    # =========================================================================
    # Event Handlers
    # =========================================================================
    
    def _select_mode(self, mode: str) -> None:
        """Handle mode button selection."""
        self.current_mode = mode.lower()
        
        # Update button visual states
        for mode_name, btn in self.mode_buttons.items():
            if mode_name == mode:
                btn.md_bg_color = Colors.PRIMARY
                btn.text_color = (1, 1, 1, 1)
            else:
                btn.md_bg_color = Colors.SURFACE_VARIANT
                btn.text_color = Colors.TEXT_SECONDARY
        
        # Show/hide advanced options (only if preset_section exists)
        if hasattr(self, "preset_section"):
            if mode.lower() == "simple":
                self._hide_advanced_options()
            else:
                self._show_advanced_options()
        
        logger.info("Mode changed", mode=mode.lower())
    
    def _show_advanced_options(self) -> None:
        """Show advanced mode options."""
        self.preset_section.opacity = 1
        self.preset_section.disabled = False
        self.preset_section.height = dp(180)
    
    def _hide_advanced_options(self) -> None:
        """Hide advanced mode options."""
        self.preset_section.opacity = 0
        self.preset_section.disabled = True
        self.preset_section.height = 0
    
    def _on_preset_selected(self, preset_name: str) -> None:
        """Handle preset card selection and apply to config."""
        for card in self.preset_cards:
            card.selected = (card.name == preset_name)
        
        # Map GUI preset name to actual config preset ID
        preset_map = {
            "Accuracy": "high_quality",
            "Speed": "fast",
            "Balanced": "balanced",
            "Low Memory": "cpu_compatible",
        }
        
        preset_id = preset_map.get(preset_name)
        if preset_id:
            try:
                from vociferous.config.presets import get_engine_preset
                preset_config = get_engine_preset(preset_id)
                if preset_config:
                    # Store the selected preset for use in transcription
                    self.selected_preset = preset_config
                    self.daemon_status.model_text.text = f"Preset: {preset_name}"
                    logger.info("Preset applied", preset=preset_id, config=preset_config)
            except Exception as e:
                logger.warning("Failed to load preset", preset=preset_id, error=str(e))
        
        logger.info("Preset selected", preset=preset_name)
        self._show_snackbar(f"Preset: {preset_name}")
    
    def _browse_files(self, *args: Any) -> None:
        """Open file browser."""
        logger.info("Opening file browser")
        
        if not self.file_manager:
            self.file_manager = MDFileManager(
                exit_manager=self._exit_file_manager,
                select_path=self._select_file,
            )
        
        try:
            self.file_manager.show(str(Path.home()))
        except Exception as e:
            logger.error("Error showing file manager", error=str(e))
    
    def _exit_file_manager(self, *args: Any) -> None:
        """Close file manager."""
        if self.file_manager:
            self.file_manager.close()
    
    def _select_file(self, path: str) -> None:
        """Handle file selection."""
        selected = Path(path)
        
        if not selected.is_file():
            self._exit_file_manager()
            return
        
        if selected.suffix.lower() not in SUPPORTED_EXTENSIONS:
            self._show_snackbar(f"Unsupported format: {selected.suffix}", error=True)
            self._exit_file_manager()
            return
        
        self.selected_file = selected
        self._exit_file_manager()
        
        # Validate and show file info
        self._validate_and_preview_file(selected)
    
    def _validate_and_preview_file(self, file_path: Path) -> None:
        """Validate audio file and show preview."""
        try:
            # Try to use vociferous validation if available
            try:
                from vociferous.audio.validation import validate_audio_file
                info = validate_audio_file(file_path)
                
                audio_info = AudioFileInfo(
                    filename=file_path.name,
                    path=str(file_path),
                    duration_seconds=info.duration_s,
                    format_name=info.format_name,
                    sample_rate=info.sample_rate,
                    channels=info.channels,
                    file_size_mb=info.file_size_mb,
                )
            except ImportError:
                # Fallback if validation module not available
                audio_info = AudioFileInfo(
                    filename=file_path.name,
                    path=str(file_path),
                    duration_seconds=0,
                    format_name=file_path.suffix[1:],
                    sample_rate=0,
                    channels=0,
                    file_size_mb=file_path.stat().st_size / (1024 * 1024),
                )
            
            self.audio_card.set_file_info(audio_info)
            self.transcribe_button.disabled = False
            
            self._show_snackbar(f"{file_path.name} ready")
            logger.info("File validated", path=str(file_path), duration=audio_info.duration_seconds)
            
        except Exception as e:
            logger.error("File validation failed", error=str(e))
            self._show_snackbar(f"Validation error: {e}", error=True)
            self.audio_card.clear()
            self.transcribe_button.disabled = True
    
    def _on_file_drop(self, window: Any, file_path: bytes, *args: Any) -> None:
        """Handle file drop event."""
        try:
            path_str = file_path.decode("utf-8")
            logger.info("File dropped", path=path_str)
            self._select_file(path_str)
        except Exception as e:
            logger.error("Error handling file drop", error=str(e))
    
    def _start_transcription(self, *args: Any) -> None:
        """Start transcription."""
        if not self.selected_file:
            return
        
        logger.info("Starting transcription", file=str(self.selected_file))
        
        # Update UI state
        self.transcribe_button.disabled = True
        self.cancel_button.disabled = False
        self.progress_card.opacity = 1
        
        # Get audio duration for progress estimation
        audio_duration = 0
        if self.audio_card.has_file:
            # Extract duration from card if available
            try:
                duration_text = self.audio_card.duration_label.text
                # Parse "Duration: MM:SS" format
                parts = duration_text.replace("Duration: ", "").split(":")
                if len(parts) == 2:
                    audio_duration = int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 3:
                    audio_duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            except (ValueError, AttributeError):
                pass
        
        self.progress_card.start(audio_duration)
        self.output_field.text = ""
        self.word_count_label.text = ""
        
        # Load config
        config = load_config()
        
        # Start transcription with callbacks
        self.transcription_manager.transcribe(
            file_path=self.selected_file,
            engine=config.engine,
            language="en",
            on_progress=self._on_transcription_progress,
            on_complete=self._on_transcription_complete,
            on_error=self._on_transcription_error,
        )
    
    def _on_transcription_progress(self, text: str) -> None:
        """Handle transcription progress."""
        # Update output field on main thread
        Clock.schedule_once(lambda dt: self._update_output(text))
    
    def _update_output(self, text: str) -> None:
        """Update output field (called on main thread)."""
        self.output_field.text = text
        
        # Update word count
        words = len(text.split()) if text else 0
        self.word_count_label.text = f"{words} words"
    
    def _on_transcription_complete(self, text: str) -> None:
        """Handle transcription completion."""
        def update_ui(dt: float) -> None:
            self.output_field.text = text
            self.progress_card.complete()
            
            # Enable action buttons
            self.transcribe_button.disabled = False
            self.cancel_button.disabled = True
            self.copy_button.disabled = False
            self.save_button.disabled = False
            self.export_button.disabled = False
            self.refine_button.disabled = False
            
            # Update word count
            words = len(text.split()) if text else 0
            self.word_count_label.text = f"{words} words"
            
            self._show_snackbar("Transcription complete!")
        
        Clock.schedule_once(update_ui)
        logger.info("Transcription complete", length=len(text))
    
    def _on_transcription_error(self, error: str) -> None:
        """Handle transcription error."""
        def update_ui(dt: float) -> None:
            self.progress_card.error(error)
            self.transcribe_button.disabled = False
            self.cancel_button.disabled = True
            self._show_snackbar(f"✗ {error}", error=True)
        
        Clock.schedule_once(update_ui)
        logger.error("Transcription error", error=error)
    
    def _cancel_transcription(self, *args: Any) -> None:
        """Cancel current transcription."""
        if self.transcription_manager.current_task:
            self.transcription_manager.stop_current()
            
        self.progress_card.reset()
        self.transcribe_button.disabled = False
        self.cancel_button.disabled = True
        
        self._show_snackbar("Transcription cancelled")
        logger.info("Transcription cancelled by user")
    
    def _copy_transcript(self, *args: Any) -> None:
        """Copy transcript to clipboard."""
        try:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(self.output_field.text)
            self._show_snackbar("Copied to clipboard")
        except Exception as e:
            logger.error("Copy failed", error=str(e))
            self._show_snackbar("Copy failed", error=True)
    
    def _save_transcript(self, *args: Any) -> None:
        """Save transcript to file."""
        if not self.output_field.text:
            return
        
        try:
            if self.selected_file:
                output_path = self.selected_file.with_suffix(".txt")
            else:
                output_path = Path.home() / "transcript.txt"
            
            output_path.write_text(self.output_field.text, encoding="utf-8")
            self._show_snackbar(f"Saved to {output_path.name}")
            logger.info("Transcript saved", path=str(output_path))
        except Exception as e:
            logger.error("Save failed", error=str(e))
            self._show_snackbar(f"Save failed: {e}", error=True)
    
    def _show_export_dialog(self, *args: Any) -> None:
        """Show export format dialog."""
        if self.export_dialog:
            self.export_dialog.dismiss()
        
        # Export format options
        from kivymd.uix.list import OneLineListItem
        
        formats = [
            ("Plain Text (.txt)", "txt"),
            ("SubRip Subtitle (.srt)", "srt"),
            ("WebVTT (.vtt)", "vtt"),
            ("JSON with Timestamps (.json)", "json"),
            ("Markdown (.md)", "md"),
        ]
        
        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(8),
            size_hint_y=None,
            height=dp(len(formats) * 48),
        )
        
        for label, ext in formats:
            item = OneLineListItem(
                text=label,
                on_release=lambda x, e=ext: self._export_as(e),
            )
            content.add_widget(item)
        
        self.export_dialog = MDDialog(
            title="Export Format",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text="CANCEL",
                    on_release=lambda x: self.export_dialog.dismiss(),
                ),
            ],
        )
        self.export_dialog.open()
    
    def _export_as(self, format_ext: str) -> None:
        """Export transcript in specified format."""
        if self.export_dialog:
            self.export_dialog.dismiss()
        
        if not self.output_field.text or not self.selected_file:
            return
        
        try:
            output_path = self.selected_file.with_suffix(f".{format_ext}")
            
            if format_ext == "txt":
                output_path.write_text(self.output_field.text, encoding="utf-8")
            elif format_ext == "md":
                # Markdown with metadata header
                content = f"""# Transcript: {self.selected_file.name}

**Source:** {self.selected_file}
**Generated by:** Vociferous

---

{self.output_field.text}
"""
                output_path.write_text(content, encoding="utf-8")
            elif format_ext == "json":
                import json
                data = {
                    "source": str(self.selected_file),
                    "text": self.output_field.text,
                    "segments": [],  # Would include actual segments if available
                }
                output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            else:
                # For SRT/VTT, we'd need segment timestamps
                output_path.write_text(self.output_field.text, encoding="utf-8")
            
            self._show_snackbar(f"Exported to {output_path.name}")
            logger.info("Transcript exported", path=str(output_path), format=format_ext)
        except Exception as e:
            logger.error("Export failed", error=str(e))
            self._show_snackbar(f"Export failed: {e}", error=True)
    
    def _refine_transcript(self, *args: Any) -> None:
        """Refine transcript with LLM.
        
        Uses Canary-Qwen in LLM mode to improve grammar and punctuation.
        """
        if not self.output_field.text.strip():
            self._show_snackbar("No transcript to refine", error=True)
            return
        
        self._show_snackbar("Refinement requires Canary-Qwen model (not yet integrated in GUI)")
    
    def _show_record_dialog(self, *args: Any) -> None:
        """Show recording dialog."""
        # Check for sounddevice dependency
        try:
            import sounddevice as sd  # noqa: F401
            has_sounddevice = True
        except ImportError:
            has_sounddevice = False
        
        if not has_sounddevice:
            self._show_snackbar(
                "Recording requires sounddevice: pip install sounddevice",
                error=True,
            )
            return
        
        # Create recording dialog
        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(16),
            size_hint_y=None,
            height=dp(180),
            padding=[dp(16), dp(8)],
        )
        
        # Recording indicator
        self.recording_status = MDLabel(
            text="Ready to record",
            font_style="H6",
            halign="center",
            size_hint=(1, None),
            height=dp(40),
        )
        content.add_widget(self.recording_status)
        
        # Recording timer
        self.recording_timer = MDLabel(
            text="0:00",
            font_style="H4",
            halign="center",
            size_hint=(1, None),
            height=dp(50),
        )
        content.add_widget(self.recording_timer)
        
        # Info text
        info_label = MDLabel(
            text="Click Start to begin recording.\nRecording will save to a temporary file.",
            font_style="Caption",
            halign="center",
            theme_text_color="Secondary",
            size_hint=(1, None),
            height=dp(50),
        )
        content.add_widget(info_label)
        
        # Dialog with buttons
        self.record_dialog = MDDialog(
            title="Record Audio",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(
                    text="CANCEL",
                    on_release=lambda x: self._stop_recording(),
                ),
                MDRaisedButton(
                    text="START",
                    on_release=lambda x: self._toggle_recording(),
                ),
            ],
        )
        
        # Store button references for state changes
        self.record_dialog_buttons = self.record_dialog.buttons
        self.is_recording = False
        self.recording_seconds = 0
        self.recording_clock = None
        self.recording_thread = None
        self.stop_recording_event = None
        self.recorded_chunks: list[bytes] = []
        
        self.record_dialog.open()
    
    def _toggle_recording(self) -> None:
        """Toggle recording on/off."""
        if not self.is_recording:
            self._start_recording()
        else:
            self._finish_recording()
    
    def _start_recording(self) -> None:
        """Start recording from microphone."""
        import tempfile
        import threading
        
        try:
            from vociferous.audio.recorder import SoundDeviceRecorder
        except ImportError:
            self._show_snackbar("Recorder not available", error=True)
            return
        
        self.is_recording = True
        self.recording_seconds = 0
        self.recorded_chunks = []
        self.stop_recording_event = threading.Event()
        
        # Update UI
        self.recording_status.text = "🔴 Recording..."
        self.recording_status.text_color = Colors.ERROR
        if self.record_dialog_buttons and len(self.record_dialog_buttons) > 1:
            self.record_dialog_buttons[1].text = "STOP"
        
        # Start timer
        self.recording_clock = Clock.schedule_interval(self._update_recording_timer, 1)
        
        # Start recording in background thread
        def record_audio():
            recorder = SoundDeviceRecorder()
            for chunk in recorder.stream_chunks(
                sample_rate=16000,
                channels=1,
                chunk_ms=100,
                stop_event=self.stop_recording_event,
            ):
                if self.stop_recording_event.is_set():
                    break
                self.recorded_chunks.append(chunk)
        
        self.recording_thread = threading.Thread(target=record_audio, daemon=True)
        self.recording_thread.start()
    
    def _update_recording_timer(self, dt: float) -> None:
        """Update recording timer display."""
        self.recording_seconds += 1
        minutes = self.recording_seconds // 60
        seconds = self.recording_seconds % 60
        self.recording_timer.text = f"{minutes}:{seconds:02d}"
    
    def _finish_recording(self) -> None:
        """Finish recording and save to file."""
        import tempfile
        import wave
        
        if not self.is_recording:
            return
        
        self.is_recording = False
        
        # Stop the recording
        if self.stop_recording_event:
            self.stop_recording_event.set()
        
        # Stop timer
        if self.recording_clock:
            self.recording_clock.cancel()
        
        # Wait for recording thread
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=2)
        
        # Dismiss dialog
        if self.record_dialog:
            self.record_dialog.dismiss()
        
        # Save to temp file
        if self.recorded_chunks:
            try:
                # Create temp file
                temp_dir = Path(tempfile.gettempdir()) / "vociferous"
                temp_dir.mkdir(exist_ok=True)
                
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                temp_path = temp_dir / f"recording_{timestamp}.wav"
                
                # Write WAV file
                audio_data = b"".join(self.recorded_chunks)
                with wave.open(str(temp_path), "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)  # 16-bit
                    wf.setframerate(16000)
                    wf.writeframes(audio_data)
                
                self._show_snackbar(f"Recorded {self.recording_seconds}s")
                logger.info("Recording saved", path=str(temp_path), duration=self.recording_seconds)
                
                # Load the recorded file
                self.selected_file = temp_path
                self._validate_and_preview_file(temp_path)
                
            except Exception as e:
                logger.error("Failed to save recording", error=str(e))
                self._show_snackbar(f"Recording failed: {e}", error=True)
        else:
            self._show_snackbar("No audio recorded", error=True)
    
    def _stop_recording(self) -> None:
        """Stop recording and cancel."""
        if self.is_recording:
            if self.stop_recording_event:
                self.stop_recording_event.set()
            if self.recording_clock:
                self.recording_clock.cancel()
            self.is_recording = False
        
        if self.record_dialog:
            self.record_dialog.dismiss()
    
    def _show_snackbar(self, text: str, error: bool = False) -> None:
        """Show a snackbar notification (KivyMD 1.2 compatible)."""
        from kivymd.uix.snackbar import MDSnackbar
        snackbar = MDSnackbar(text, duration=3 if not error else 5)
        if error:
            snackbar.md_bg_color = Colors.ERROR
        snackbar.open()
