"""Enhanced error dialogs with structured information.

Implements:
- Structured error display with expandable details
- Numbered recovery suggestions
- Copy-to-clipboard functionality
- Different severity levels (error, warning, info)
- Integration with domain error serialization
"""

from __future__ import annotations

from typing import Any

import structlog
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.properties import StringProperty, BooleanProperty, ObjectProperty
from kivy.uix.modalview import ModalView
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDRaisedButton, MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.list import TwoLineListItem
from kivymd.uix.scrollview import MDScrollView

from .widgets import Colors

logger = structlog.get_logger(__name__)


class ErrorDialog(ModalView):
    """Enhanced error dialog with structured error display.
    
    Features:
    - Title with severity icon
    - Error message with details
    - Expandable technical details
    - Numbered recovery suggestions
    - Copy error info button
    - Retry action (optional)
    """
    
    title = StringProperty("")
    message = StringProperty("")
    details = StringProperty("")
    suggestions = ObjectProperty([])
    severity = StringProperty("error")  # error, warning, info
    show_retry = BooleanProperty(False)
    
    def __init__(
        self,
        title: str,
        message: str,
        details: str = "",
        suggestions: list[str] | None = None,
        severity: str = "error",
        show_retry: bool = False,
        on_retry: Any = None,
        on_dismiss: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.title = title
        self.message = message
        self.details = details
        self.suggestions = suggestions or []
        self.severity = severity
        self.show_retry = show_retry
        self.on_retry_callback = on_retry
        self.on_dismiss_callback = on_dismiss
        
        self.size_hint = (0.85, None)
        self.auto_dismiss = False
        self._details_expanded = False
        
        self._build_ui()
    
    def _get_severity_icon(self) -> str:
        """Get the icon for the current severity level."""
        icons = {
            "error": "[X]",
            "warning": "[!]",
            "info": "[i]",
        }
        return icons.get(self.severity, "[X]")
    
    def _get_severity_color(self) -> tuple[float, float, float, float]:
        """Get the color for the current severity level."""
        colors = {
            "error": Colors.ERROR,
            "warning": Colors.WARNING,
            "info": Colors.INFO,
        }
        return colors.get(self.severity, Colors.ERROR)
    
    def _build_ui(self) -> None:
        """Build the dialog UI."""
        # Main card
        card = MDCard(
            orientation="vertical",
            padding=[dp(20), dp(16)],
            spacing=dp(12),
            size_hint=(1, None),
            radius=[dp(16)],
        )
        card.md_bg_color = Colors.SURFACE
        card.bind(minimum_height=card.setter("height"))
        
        # Header with icon and title
        header = MDBoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(40),
            spacing=dp(8),
        )
        
        severity_icon = MDLabel(
            text=self._get_severity_icon(),
            font_style="H5",
            size_hint=(None, 1),
            width=dp(40),
            valign="center",
        )
        header.add_widget(severity_icon)
        
        title_label = MDLabel(
            text=f"[b]{self.title}[/b]",
            markup=True,
            font_style="H6",
            theme_text_color="Primary",
            size_hint=(1, 1),
            valign="center",
        )
        header.add_widget(title_label)
        
        # Copy button
        copy_button = MDIconButton(
            icon="content-copy",
            on_release=self._copy_to_clipboard,
        )
        header.add_widget(copy_button)
        
        card.add_widget(header)
        
        # Separator line
        separator = MDBoxLayout(
            size_hint=(1, None),
            height=dp(1),
        )
        separator.md_bg_color = self._get_severity_color()
        card.add_widget(separator)
        
        # Message
        message_label = MDLabel(
            text=self.message,
            font_style="Body1",
            theme_text_color="Primary",
            size_hint=(1, None),
            halign="left",
        )
        message_label.bind(texture_size=lambda *x: setattr(
            message_label, "height", message_label.texture_size[1] + dp(8)
        ))
        card.add_widget(message_label)
        
        # Details (expandable)
        if self.details:
            details_button = MDFlatButton(
                text="▶ Show technical details",
                on_release=self._toggle_details,
            )
            self.details_button = details_button
            card.add_widget(details_button)
            
            details_card = MDCard(
                orientation="vertical",
                padding=[dp(12), dp(8)],
                size_hint=(1, None),
                height=dp(0),
                radius=[dp(8)],
            )
            details_card.md_bg_color = Colors.SURFACE_VARIANT
            
            details_scroll = MDScrollView(
                size_hint=(1, None),
                height=dp(100),
            )
            
            details_text = MDLabel(
                text=f"[font=monospace]{self.details}[/font]",
                markup=True,
                font_style="Caption",
                theme_text_color="Secondary",
                size_hint_y=None,
                text_size=(None, None),
            )
            details_text.bind(texture_size=lambda *x: setattr(
                details_text, "height", details_text.texture_size[1]
            ))
            self.details_text = details_text
            
            details_scroll.add_widget(details_text)
            details_card.add_widget(details_scroll)
            
            self.details_card = details_card
            card.add_widget(details_card)
        
        # Suggestions
        if self.suggestions:
            suggestions_label = MDLabel(
                text="[b]💡 Suggestions:[/b]",
                markup=True,
                font_style="Subtitle2",
                size_hint=(1, None),
                height=dp(32),
            )
            card.add_widget(suggestions_label)
            
            for i, suggestion in enumerate(self.suggestions, 1):
                suggestion_item = MDLabel(
                    text=f"  {i}. {suggestion}",
                    font_style="Body2",
                    theme_text_color="Secondary",
                    size_hint=(1, None),
                    halign="left",
                )
                suggestion_item.bind(texture_size=lambda *x, s=suggestion_item: setattr(
                    s, "height", s.texture_size[1] + dp(4)
                ))
                card.add_widget(suggestion_item)
        
        # Buttons
        button_layout = MDBoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(48),
            spacing=dp(12),
            padding=[0, dp(8), 0, 0],
        )
        
        if self.show_retry:
            retry_button = MDRaisedButton(
                text="🔄 Retry",
                on_release=self._on_retry,
            )
            button_layout.add_widget(retry_button)
        
        dismiss_button = MDRaisedButton(
            text="OK",
            on_release=self._on_close,
        )
        button_layout.add_widget(dismiss_button)
        
        card.add_widget(button_layout)
        
        self.add_widget(card)
        
        # Set initial height
        Clock.schedule_once(self._update_height, 0.1)
    
    def _update_height(self, *args: Any) -> None:
        """Update dialog height based on content."""
        # Calculate approximate height
        base_height = dp(200)
        
        if self.details:
            base_height += dp(40)
        
        if self.suggestions:
            base_height += dp(32 + len(self.suggestions) * 28)
        
        if self._details_expanded:
            base_height += dp(120)
        
        self.height = min(base_height, dp(500))
    
    def _toggle_details(self, *args: Any) -> None:
        """Toggle details visibility."""
        self._details_expanded = not self._details_expanded
        
        if self._details_expanded:
            self.details_card.height = dp(120)
            self.details_button.text = "▼ Hide technical details"
        else:
            self.details_card.height = dp(0)
            self.details_button.text = "▶ Show technical details"
        
        self._update_height()
    
    def _copy_to_clipboard(self, *args: Any) -> None:
        """Copy error information to clipboard."""
        error_text = f"""Error: {self.title}
Message: {self.message}
"""
        if self.details:
            error_text += f"\nTechnical Details:\n{self.details}"
        
        if self.suggestions:
            error_text += "\n\nSuggestions:\n"
            for i, s in enumerate(self.suggestions, 1):
                error_text += f"  {i}. {s}\n"
        
        Clipboard.copy(error_text)
        
        # Show confirmation
        from kivymd.uix.snackbar import MDSnackbar
        snackbar = MDSnackbar("Error info copied to clipboard", duration=2)
        snackbar.open()
    
    def _on_retry(self, *args: Any) -> None:
        """Handle retry button press."""
        self.dismiss()
        if self.on_retry_callback:
            self.on_retry_callback()
    
    def _on_close(self, *args: Any) -> None:
        """Handle close button press."""
        self.dismiss()
        if self.on_dismiss_callback:
            self.on_dismiss_callback()


class QuickErrorDialog(ModalView):
    """Simple error dialog for quick notifications.
    
    Use for non-critical errors that don't need detailed recovery steps.
    """
    
    def __init__(
        self,
        message: str,
        severity: str = "error",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.message = message
        self.severity = severity
        
        self.size_hint = (0.7, None)
        self.height = dp(140)
        self.auto_dismiss = True
        
        self._build_ui()
    
    def _build_ui(self) -> None:
        """Build the quick dialog UI."""
        icons = {"error": "[X]", "warning": "[!]", "info": "[i]", "success": "OK"}
        colors = {
            "error": Colors.ERROR,
            "warning": Colors.WARNING,
            "info": Colors.INFO,
            "success": Colors.SUCCESS,
        }
        
        card = MDCard(
            orientation="vertical",
            padding=[dp(16), dp(12)],
            spacing=dp(8),
            size_hint=(1, 1),
            radius=[dp(12)],
        )
        card.md_bg_color = Colors.SURFACE
        
        # Icon and message
        content = MDBoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(60),
            spacing=dp(12),
        )
        
        icon_label = MDLabel(
            text=icons.get(self.severity, "[X]"),
            font_style="H4",
            size_hint=(None, 1),
            width=dp(48),
            valign="center",
            halign="center",
        )
        content.add_widget(icon_label)
        
        message_label = MDLabel(
            text=self.message,
            font_style="Body1",
            theme_text_color="Primary",
            size_hint=(1, 1),
            valign="center",
        )
        content.add_widget(message_label)
        
        card.add_widget(content)
        
        # OK button
        button = MDRaisedButton(
            text="OK",
            size_hint=(1, None),
            height=dp(40),
            on_release=self.dismiss,
        )
        card.add_widget(button)
        
        self.add_widget(card)


def show_error(
    title: str,
    message: str,
    details: str = "",
    suggestions: list[str] | None = None,
    severity: str = "error",
    show_retry: bool = False,
    on_retry: Any = None,
    on_dismiss: Any = None,
) -> ErrorDialog:
    """Show an enhanced error dialog.
    
    Args:
        title: Dialog title
        message: Main error message
        details: Technical details (expandable)
        suggestions: List of numbered recovery suggestions
        severity: "error", "warning", or "info"
        show_retry: Whether to show retry button
        on_retry: Callback for retry button
        on_dismiss: Callback for dismiss
    
    Returns:
        The ErrorDialog instance
    """
    dialog = ErrorDialog(
        title=title,
        message=message,
        details=details,
        suggestions=suggestions,
        severity=severity,
        show_retry=show_retry,
        on_retry=on_retry,
        on_dismiss=on_dismiss,
    )
    dialog.open()
    return dialog


def show_quick_error(message: str, severity: str = "error") -> QuickErrorDialog:
    """Show a quick error notification.
    
    Args:
        message: The error message
        severity: "error", "warning", "info", or "success"
    
    Returns:
        The QuickErrorDialog instance
    """
    dialog = QuickErrorDialog(message=message, severity=severity)
    dialog.open()
    return dialog


def show_error_from_exception(
    exc: Exception,
    show_retry: bool = False,
    on_retry: Any = None,
) -> ErrorDialog:
    """Show an error dialog from an exception.
    
    Uses domain error serialization if available.
    
    Args:
        exc: The exception to display
        show_retry: Whether to show retry button
        on_retry: Callback for retry button
    
    Returns:
        The ErrorDialog instance
    """
    try:
        from vociferous.domain.error_serialization import format_error_for_dialog
        
        error_info = format_error_for_dialog(exc)
        return show_error(
            title=error_info.get("title", "Error"),
            message=error_info.get("message", str(exc)),
            details=error_info.get("details", ""),
            suggestions=error_info.get("suggestions", []),
            severity=error_info.get("severity", "error"),
            show_retry=show_retry,
            on_retry=on_retry,
        )
    except ImportError:
        # Fallback for when error serialization isn't available
        return show_error(
            title="Error",
            message=str(exc),
            details=type(exc).__name__,
            suggestions=["Check the logs for more information"],
            severity="error",
            show_retry=show_retry,
            on_retry=on_retry,
        )


class TranscriptionErrorDialog(ErrorDialog):
    """Specialized error dialog for transcription failures.
    
    Includes transcription-specific recovery suggestions.
    """
    
    def __init__(
        self,
        message: str,
        stage: str = "unknown",
        audio_file: str = "",
        **kwargs: Any,
    ) -> None:
        # Build transcription-specific suggestions
        suggestions = self._build_suggestions(stage, audio_file)
        
        super().__init__(
            title=f"Transcription Failed ({stage.title()})",
            message=message,
            suggestions=suggestions,
            severity="error",
            **kwargs,
        )
    
    def _build_suggestions(self, stage: str, audio_file: str) -> list[str]:
        """Build stage-specific recovery suggestions."""
        base_suggestions = [
            "Check that the audio file exists and is readable",
            "Try a different audio file to isolate the issue",
        ]
        
        stage_suggestions = {
            "decode": [
                "Ensure ffmpeg is installed (vociferous check)",
                "Try converting the file manually: ffmpeg -i input.mp3 output.wav",
            ],
            "vad": [
                "Check if the audio contains speech",
                "Try adjusting VAD sensitivity in settings",
            ],
            "condense": [
                "This may indicate corrupted VAD output",
                "Try running with verbose logging",
            ],
            "transcribe": [
                "Check GPU memory usage (nvidia-smi)",
                "Try a smaller model or reduce batch size",
                "Ensure the ASR engine is properly installed",
            ],
            "refine": [
                "Refinement uses the Canary LLM mode",
                "Check available GPU memory",
                "Skip refinement if not needed",
            ],
        }
        
        return base_suggestions + stage_suggestions.get(stage, [])


def show_transcription_error(
    message: str,
    stage: str = "unknown",
    audio_file: str = "",
    show_retry: bool = True,
    on_retry: Any = None,
) -> TranscriptionErrorDialog:
    """Show a transcription-specific error dialog.
    
    Args:
        message: The error message
        stage: The pipeline stage that failed (decode, vad, condense, transcribe, refine)
        audio_file: The audio file path (for context)
        show_retry: Whether to show retry button
        on_retry: Callback for retry button
    
    Returns:
        The TranscriptionErrorDialog instance
    """
    dialog = TranscriptionErrorDialog(
        message=message,
        stage=stage,
        audio_file=audio_file,
        show_retry=show_retry,
        on_retry=on_retry,
    )
    dialog.open()
    return dialog
