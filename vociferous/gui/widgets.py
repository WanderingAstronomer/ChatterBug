"""Reusable UI widgets for Vociferous GUI.

This module provides enhanced, reusable widgets built on KivyMD components
for a consistent, beautiful user experience throughout the application.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import (
    BooleanProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDIconButton, MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.tooltip import MDTooltip

__all__ = [
    "AudioFileCard",
    "DaemonStatusWidget",
    "PipelineStageIndicator",
    "PresetCard",
    "ProgressCard",
    "TooltipButton",
    "TooltipIconButton",
]


# =============================================================================
# Color Constants (Material Design 3 aligned)
# =============================================================================

class Colors:
    """Material Design color constants."""
    
    # Status colors
    SUCCESS = "#4CAF50"       # Green
    WARNING = "#FF9800"       # Orange
    ERROR = "#F44336"         # Red
    INFO = "#2196F3"          # Blue
    
    # Surface colors (dark theme)
    SURFACE = "#1E1E1E"
    SURFACE_VARIANT = "#2D2D2D"
    SURFACE_BRIGHT = "#3D3D3D"
    
    # Accent colors
    PRIMARY = "#2196F3"       # Blue 500
    PRIMARY_VARIANT = "#1976D2"  # Blue 700
    SECONDARY = "#03DAC6"     # Teal
    
    # Text colors
    TEXT_PRIMARY = "#FFFFFF"
    TEXT_SECONDARY = "#B3B3B3"
    TEXT_DISABLED = "#666666"


# =============================================================================
# Base Enhanced Widgets
# =============================================================================

class TooltipButton(MDRaisedButton, MDTooltip):
    """Material button with tooltip support."""
    
    tooltip_text = StringProperty("")


class TooltipIconButton(MDIconButton, MDTooltip):
    """Icon button with tooltip support."""
    
    tooltip_text = StringProperty("")


# =============================================================================
# Audio File Preview Card
# =============================================================================

@dataclass
class AudioFileInfo:
    """Audio file metadata for display."""
    
    filename: str
    path: str
    duration_seconds: float
    format_name: str
    sample_rate: int
    channels: int
    file_size_mb: float
    
    @property
    def duration_formatted(self) -> str:
        """Format duration as MM:SS or HH:MM:SS."""
        total_seconds = int(self.duration_seconds)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"
    
    @property
    def channels_text(self) -> str:
        """Human-readable channel count."""
        return "Stereo" if self.channels >= 2 else "Mono"


class AudioFileCard(MDCard):
    """Card displaying audio file metadata.
    
    Shows filename, duration, format, sample rate, channels, and file size
    in a visually appealing card layout.
    """
    
    has_file = BooleanProperty(False)
    
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = [dp(16), dp(12)]
        self.spacing = dp(8)
        self.size_hint = (1, None)
        self.height = dp(140)
        self.elevation = 2
        self.radius = [dp(12)]
        self.md_bg_color = Colors.SURFACE_VARIANT
        
        self._build_ui()
    
    def _build_ui(self) -> None:
        """Build the card UI."""
        # Header row with icon and filename
        header = MDBoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(40),
            spacing=dp(8),
        )
        
        self.file_icon = MDLabel(
            text="[?]",
            font_style="H5",
            size_hint=(None, 1),
            width=dp(40),
            halign="center",
            valign="center",
        )
        header.add_widget(self.file_icon)
        
        self.filename_label = MDLabel(
            text="No file selected",
            font_style="H6",
            theme_text_color="Primary",
            halign="left",
            valign="center",
            size_hint=(1, 1),
            shorten=True,
            shorten_from="right",
        )
        header.add_widget(self.filename_label)
        
        self.add_widget(header)
        
        # Metadata row 1: Duration | Format | Size
        meta_row1 = MDBoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(30),
            spacing=dp(16),
        )
        
        self.duration_label = self._create_meta_label("Duration: --:--")
        self.format_label = self._create_meta_label("Format: ---")
        self.size_label = self._create_meta_label("Size: -- MB")
        
        meta_row1.add_widget(self.duration_label)
        meta_row1.add_widget(self.format_label)
        meta_row1.add_widget(self.size_label)
        
        self.add_widget(meta_row1)
        
        # Metadata row 2: Sample Rate | Channels
        meta_row2 = MDBoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(30),
            spacing=dp(16),
        )
        
        self.sample_rate_label = self._create_meta_label("Rate: --- Hz")
        self.channels_label = self._create_meta_label("Channels: ---")
        
        meta_row2.add_widget(self.sample_rate_label)
        meta_row2.add_widget(self.channels_label)
        meta_row2.add_widget(MDLabel())  # Spacer
        
        self.add_widget(meta_row2)
    
    def _create_meta_label(self, text: str) -> MDLabel:
        """Create a styled metadata label."""
        return MDLabel(
            text=text,
            font_style="Body2",
            theme_text_color="Secondary",
            size_hint=(None, 1),
            width=dp(120),
        )
    
    def set_file_info(self, info: AudioFileInfo) -> None:
        """Update card with audio file information."""
        self.has_file = True
        self.file_icon.text = "[audio]"
        self.filename_label.text = info.filename
        self.duration_label.text = f"Duration: {info.duration_formatted}"
        self.format_label.text = f"Format: {info.format_name.upper()}"
        self.size_label.text = f"Size: {info.file_size_mb:.1f} MB"
        self.sample_rate_label.text = f"Rate: {info.sample_rate // 1000}kHz"
        self.channels_label.text = f"Channels: {info.channels_text}"
        
        # Update card color to indicate valid file
        self.md_bg_color = Colors.SURFACE_VARIANT
    
    def clear(self) -> None:
        """Clear the card to empty state."""
        self.has_file = False
        self.file_icon.text = "[file]"
        self.filename_label.text = "No file selected"
        self.duration_label.text = "Duration: --:--"
        self.format_label.text = "Format: ---"
        self.size_label.text = "Size: -- MB"
        self.sample_rate_label.text = "Rate: --- Hz"
        self.channels_label.text = "Channels: ---"
        self.md_bg_color = Colors.SURFACE_VARIANT


# =============================================================================
# Pipeline Stage Indicator
# =============================================================================

class PipelineStageIndicator(MDBoxLayout):
    """Visual indicator showing pipeline progress through stages.
    
    Displays: Decode → VAD → Condense → Transcribe → Refine
    with highlighted current stage and completed stages.
    """
    
    STAGES = ["Decode", "VAD", "Condense", "Transcribe", "Refine"]
    
    current_stage = NumericProperty(-1)  # -1 = not started
    
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint = (1, None)
        self.height = dp(50)
        self.spacing = dp(4)
        self.padding = [dp(8), dp(8)]
        
        self.stage_labels: list[MDLabel] = []
        self.arrow_labels: list[MDLabel] = []
        
        self._build_ui()
    
    def _build_ui(self) -> None:
        """Build the stage indicator UI."""
        for i, stage in enumerate(self.STAGES):
            # Add stage label
            label = MDLabel(
                text=stage,
                font_style="Caption",
                halign="center",
                valign="center",
                size_hint=(1, 1),
                theme_text_color="Secondary",
            )
            self.stage_labels.append(label)
            self.add_widget(label)
            
            # Add arrow between stages (except after last)
            if i < len(self.STAGES) - 1:
                arrow = MDLabel(
                    text="→",
                    font_style="Caption",
                    halign="center",
                    valign="center",
                    size_hint=(None, 1),
                    width=dp(20),
                    theme_text_color="Secondary",
                )
                self.arrow_labels.append(arrow)
                self.add_widget(arrow)
        
        self._update_stage_colors()
    
    def _update_stage_colors(self) -> None:
        """Update stage label colors based on current stage."""
        for i, label in enumerate(self.stage_labels):
            if i < self.current_stage:
                # Completed stage
                label.theme_text_color = "Custom"
                label.text_color = Colors.SUCCESS
                label.text = f"[done] {self.STAGES[i]}"
            elif i == self.current_stage:
                # Current stage
                label.theme_text_color = "Custom"
                label.text_color = Colors.PRIMARY
                label.text = f"● {self.STAGES[i]}"
            else:
                # Future stage
                label.theme_text_color = "Secondary"
                label.text = self.STAGES[i]
    
    def on_current_stage(self, instance: Any, value: int) -> None:
        """Handle stage change."""
        self._update_stage_colors()
    
    def set_stage(self, stage_name: str) -> None:
        """Set the current stage by name."""
        try:
            index = self.STAGES.index(stage_name.title())
            self.current_stage = index
        except ValueError:
            pass  # Unknown stage
    
    def reset(self) -> None:
        """Reset to initial state."""
        self.current_stage = -1
    
    def complete(self) -> None:
        """Mark all stages as complete."""
        self.current_stage = len(self.STAGES)


# =============================================================================
# Progress Card with Metrics
# =============================================================================

class ProgressCard(MDCard):
    """Progress display card with metrics.
    
    Shows:
    - Overall progress bar
    - Current stage
    - Elapsed time
    - Estimated remaining time
    - Real-time factor (RTF)
    """
    
    progress = NumericProperty(0)  # 0-100
    is_running = BooleanProperty(False)
    
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = [dp(16), dp(12)]
        self.spacing = dp(8)
        self.size_hint = (1, None)
        self.height = dp(140)
        self.elevation = 2
        self.radius = [dp(12)]
        self.md_bg_color = Colors.SURFACE_VARIANT
        
        self._start_time: float = 0
        self._audio_duration: float = 0
        self._clock_event: Any = None
        
        self._build_ui()
    
    def _build_ui(self) -> None:
        """Build the progress card UI."""
        # Header
        header = MDBoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(30),
        )
        
        self.status_label = MDLabel(
            text="Ready",
            font_style="Subtitle1",
            theme_text_color="Primary",
            halign="left",
        )
        header.add_widget(self.status_label)
        
        self.percentage_label = MDLabel(
            text="",
            font_style="Subtitle1",
            theme_text_color="Secondary",
            halign="right",
            size_hint=(None, 1),
            width=dp(60),
        )
        header.add_widget(self.percentage_label)
        
        self.add_widget(header)
        
        # Progress bar
        self.progress_bar = MDProgressBar(
            value=0,
            size_hint=(1, None),
            height=dp(6),
        )
        self.add_widget(self.progress_bar)
        
        # Metrics row
        metrics_row = MDBoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(30),
            spacing=dp(16),
        )
        
        self.elapsed_label = MDLabel(
            text="Elapsed: --:--",
            font_style="Caption",
            theme_text_color="Secondary",
            size_hint=(1, 1),
        )
        metrics_row.add_widget(self.elapsed_label)
        
        self.remaining_label = MDLabel(
            text="Remaining: --:--",
            font_style="Caption",
            theme_text_color="Secondary",
            size_hint=(1, 1),
            halign="center",
        )
        metrics_row.add_widget(self.remaining_label)
        
        self.rtf_label = MDLabel(
            text="RTF: --",
            font_style="Caption",
            theme_text_color="Secondary",
            size_hint=(1, 1),
            halign="right",
        )
        metrics_row.add_widget(self.rtf_label)
        
        self.add_widget(metrics_row)
        
        # Pipeline stage indicator
        self.stage_indicator = PipelineStageIndicator()
        self.add_widget(self.stage_indicator)
    
    def start(self, audio_duration: float = 0) -> None:
        """Start progress tracking."""
        import time
        self._start_time = time.time()
        self._audio_duration = audio_duration
        self.is_running = True
        self.progress = 0
        self.status_label.text = "Starting..."
        self.stage_indicator.reset()
        
        # Start clock update
        self._clock_event = Clock.schedule_interval(self._update_time, 0.5)
    
    def _update_time(self, dt: float) -> None:
        """Update elapsed time display."""
        import time
        elapsed = time.time() - self._start_time
        self.elapsed_label.text = f"Elapsed: {self._format_time(elapsed)}"
        
        # Calculate RTF if we have audio duration and progress
        if self._audio_duration > 0 and self.progress > 0:
            audio_processed = self._audio_duration * (self.progress / 100)
            if audio_processed > 0:
                rtf = elapsed / audio_processed
                self.rtf_label.text = f"RTF: {rtf:.2f}x"
                
                # Estimate remaining time
                if self.progress < 100:
                    remaining = elapsed * (100 - self.progress) / self.progress
                    self.remaining_label.text = f"Remaining: {self._format_time(remaining)}"
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS or HH:MM:SS."""
        total = int(seconds)
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"
    
    def update(self, progress: float, stage: str, message: str = "") -> None:
        """Update progress display."""
        self.progress = progress
        self.progress_bar.value = progress
        self.percentage_label.text = f"{progress:.0f}%"
        
        if message:
            self.status_label.text = message
        
        self.stage_indicator.set_stage(stage)
    
    def complete(self) -> None:
        """Mark progress as complete."""
        self.progress = 100
        self.progress_bar.value = 100
        self.percentage_label.text = "100%"
        self.status_label.text = "Complete!"
        self.status_label.theme_text_color = "Custom"
        self.status_label.text_color = Colors.SUCCESS
        self.remaining_label.text = "Remaining: 0:00"
        self.is_running = False
        self.stage_indicator.complete()
        
        if self._clock_event:
            self._clock_event.cancel()
    
    def error(self, message: str) -> None:
        """Show error state."""
        self.status_label.text = f"Error: {message}"
        self.status_label.theme_text_color = "Custom"
        self.status_label.text_color = Colors.ERROR
        self.is_running = False
        
        if self._clock_event:
            self._clock_event.cancel()
    
    def reset(self) -> None:
        """Reset to initial state."""
        self.progress = 0
        self.progress_bar.value = 0
        self.percentage_label.text = ""
        self.status_label.text = "Ready"
        self.status_label.theme_text_color = "Primary"
        self.elapsed_label.text = "Elapsed: --:--"
        self.remaining_label.text = "Remaining: --:--"
        self.rtf_label.text = "RTF: --"
        self.is_running = False
        self.stage_indicator.reset()
        
        if self._clock_event:
            self._clock_event.cancel()


# =============================================================================
# Daemon Status Widget
# =============================================================================

class DaemonStatusWidget(MDCard):
    """Persistent daemon status indicator.
    
    Shows:
    - Daemon state (running/stopped/starting)
    - Model loaded
    - VRAM usage
    - Uptime
    """
    
    STATUS_COLORS = {
        "running": Colors.SUCCESS,
        "starting": Colors.WARNING,
        "stopped": Colors.TEXT_DISABLED,
        "error": Colors.ERROR,
    }
    
    status = StringProperty("stopped")
    
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.padding = [dp(12), dp(8)]
        self.spacing = dp(8)
        self.size_hint = (1, None)
        self.height = dp(50)
        self.elevation = 1
        self.radius = [dp(8)]
        self.md_bg_color = Colors.SURFACE_VARIANT
        
        self._build_ui()
    
    def _build_ui(self) -> None:
        """Build the daemon status UI."""
        # Status indicator (text-based for compatibility)
        self.status_dot = MDLabel(
            text="[--]",
            font_style="Body2",
            theme_text_color="Custom",
            text_color=Colors.TEXT_DISABLED,
            size_hint=(None, 1),
            width=dp(36),
            halign="center",
            valign="center",
        )
        self.add_widget(self.status_dot)
        
        # Status text
        info_layout = MDBoxLayout(
            orientation="vertical",
            size_hint=(1, 1),
            spacing=dp(0),
        )
        
        self.status_text = MDLabel(
            text="Daemon: Stopped",
            font_style="Body2",
            theme_text_color="Primary",
            size_hint=(1, 0.5),
            valign="bottom",
        )
        info_layout.add_widget(self.status_text)
        
        self.model_text = MDLabel(
            text="No model loaded",
            font_style="Caption",
            theme_text_color="Secondary",
            size_hint=(1, 0.5),
            valign="top",
        )
        info_layout.add_widget(self.model_text)
        
        self.add_widget(info_layout)
        
        # VRAM usage
        self.vram_label = MDLabel(
            text="",
            font_style="Caption",
            theme_text_color="Secondary",
            size_hint=(None, 1),
            width=dp(80),
            halign="right",
            valign="center",
        )
        self.add_widget(self.vram_label)
        
        # Start/stop button
        self.action_button = TooltipIconButton(
            icon="play",
            on_release=self._toggle_daemon,
        )
        self.action_button.tooltip_text = "Start daemon"
        self.add_widget(self.action_button)
    
    def on_status(self, instance: Any, value: str) -> None:
        """Handle status change."""
        color = self.STATUS_COLORS.get(value, Colors.TEXT_DISABLED)
        self.status_dot.text_color = color
        
        if value == "running":
            self.status_text.text = "Daemon: Running"
            self.status_dot.text = "[OK]"
            self.action_button.icon = "stop"
            self.action_button.tooltip_text = "Stop daemon"
        elif value == "starting":
            self.status_text.text = "Daemon: Starting..."
            self.status_dot.text = "[..]"
            self.action_button.icon = "loading"
        elif value == "error":
            self.status_text.text = "Daemon: Error"
            self.status_dot.text = "[!!]"
            self.action_button.icon = "refresh"
            self.action_button.tooltip_text = "Retry"
        else:
            self.status_text.text = "Daemon: Stopped"
            self.status_dot.text = "[--]"
            self.action_button.icon = "play"
            self.action_button.tooltip_text = "Start daemon"
    
    def set_running(self, model_name: str, vram_gb: float = 0) -> None:
        """Set running status with model info."""
        self.status = "running"
        self.model_text.text = f"Model: {model_name}"
        if vram_gb > 0:
            self.vram_label.text = f"VRAM: {vram_gb:.1f}GB"
    
    def set_starting(self) -> None:
        """Set starting status."""
        self.status = "starting"
        self.model_text.text = "Loading model..."
        self.vram_label.text = ""
    
    def set_stopped(self) -> None:
        """Set stopped status."""
        self.status = "stopped"
        self.model_text.text = "No model loaded"
        self.vram_label.text = ""
    
    def set_error(self, message: str) -> None:
        """Set error status."""
        self.status = "error"
        self.model_text.text = f"Error: {message}"
    
    def _toggle_daemon(self, *args: Any) -> None:
        """Toggle daemon state - start or stop the transcription daemon."""
        import threading
        
        if self.status == "running":
            # Stop the daemon (simulated)
            self.set_stopped()
            return
        
        if self.status in {"stopped", "error"}:
            # Start the daemon (simulated async to avoid UI freeze)
            self.set_starting()
            
            def start_daemon_async() -> None:
                import time
                time.sleep(1)
                Clock.schedule_once(
                    lambda dt: self.set_running("Whisper Turbo", 2.1),
                    0,
                )
            
            threading.Thread(target=start_daemon_async, daemon=True).start()


# =============================================================================
# Preset Card
# =============================================================================

class PresetCard(MDCard):
    """Visual preset selector card.
    
    Displays preset name, description, and configuration summary.
    Highlights when selected.
    """
    
    selected = BooleanProperty(False)
    
    def __init__(
        self,
        name: str,
        description: str,
        icon: str = "tune",
        on_select: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.name = name
        self.description = description
        self.icon = icon
        self.on_select_callback = on_select
        
        self.orientation = "vertical"
        self.padding = [dp(16), dp(12)]
        self.spacing = dp(4)
        self.size_hint = (None, None)
        self.size = (dp(180), dp(100))
        self.elevation = 2
        self.radius = [dp(12)]
        self.ripple_behavior = True
        
        self._build_ui()
        self._update_style()
        
        self.bind(on_release=self._on_tap)
    
    def _build_ui(self) -> None:
        """Build the preset card UI."""
        # Header with icon
        header = MDBoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(32),
            spacing=dp(8),
        )
        
        self.icon_label = MDLabel(
            text=self._get_icon_emoji(),
            font_style="H6",
            size_hint=(None, 1),
            width=dp(28),
            halign="center",
            valign="center",
        )
        header.add_widget(self.icon_label)
        
        self.name_label = MDLabel(
            text=self.name,
            font_style="Subtitle1",
            theme_text_color="Primary",
            halign="left",
            valign="center",
            size_hint=(1, 1),
        )
        header.add_widget(self.name_label)
        
        self.add_widget(header)
        
        # Description
        self.desc_label = MDLabel(
            text=self.description,
            font_style="Caption",
            theme_text_color="Secondary",
            halign="left",
            size_hint=(1, 1),
        )
        self.add_widget(self.desc_label)
    
    def _get_icon_emoji(self) -> str:
        """Return empty string - icons removed for compatibility."""
        return ""
    
    def _update_style(self) -> None:
        """Update card style based on selection state."""
        if self.selected:
            self.md_bg_color = Colors.PRIMARY_VARIANT
            self.elevation = 4
        else:
            self.md_bg_color = Colors.SURFACE_VARIANT
            self.elevation = 2
    
    def on_selected(self, instance: Any, value: bool) -> None:
        """Handle selection change."""
        self._update_style()
    
    def _on_tap(self, *args: Any) -> None:
        """Handle tap on card."""
        if self.on_select_callback:
            self.on_select_callback(self.name)
