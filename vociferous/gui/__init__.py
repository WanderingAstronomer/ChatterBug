"""KivyMD-based GUI for Vociferous."""

from .animations import (
    AnimatedProgressBar,
    FadeTransition,
    LoadingSpinner,
    PulseAnimation,
    ShakeAnimation,
    SlideAnimation,
    StaggeredAnimation,
    SuccessAnimation,
)
from .app import VociferousGUIApp
from .config_schema import (
    FIELD_METADATA,
    ConfigFieldSchema,
    get_config_schema,
)
from .error_dialogs import (
    ErrorDialog,
    QuickErrorDialog,
    TranscriptionErrorDialog,
    show_error,
    show_error_from_exception,
    show_quick_error,
    show_transcription_error,
)
from .errors import (
    DialogErrorData,
    format_error_for_dialog,
)
from .history_screen import HistoryScreen
from .home_screen import EnhancedHomeScreen
from .settings_screen import EnhancedSettingsScreen
from .validation import (
    ValidationErrorInfo,
    format_validation_errors,
    validate_config_value,
)
from .widgets import (
    AudioFileCard,
    Colors,
    DaemonStatusWidget,
    PipelineStageIndicator,
    PresetCard,
    ProgressCard,
    TooltipButton,
    TooltipIconButton,
)

__all__ = [
    # App
    "VociferousGUIApp",
    # Screens
    "EnhancedHomeScreen",
    "EnhancedSettingsScreen",
    "HistoryScreen",
    # Widgets
    "AudioFileCard",
    "Colors",
    "DaemonStatusWidget",
    "PipelineStageIndicator",
    "PresetCard",
    "ProgressCard",
    "TooltipButton",
    "TooltipIconButton",
    # Animations
    "AnimatedProgressBar",
    "FadeTransition",
    "LoadingSpinner",
    "PulseAnimation",
    "ShakeAnimation",
    "SlideAnimation",
    "StaggeredAnimation",
    "SuccessAnimation",
    # Error dialogs
    "ErrorDialog",
    "QuickErrorDialog",
    "TranscriptionErrorDialog",
    "show_error",
    "show_error_from_exception",
    "show_quick_error",
    "show_transcription_error",
    # Config/Validation
    "ConfigFieldSchema",
    "DialogErrorData",
    "FIELD_METADATA",
    "ValidationErrorInfo",
    "format_error_for_dialog",
    "format_validation_errors",
    "get_config_schema",
    "validate_config_value",
]
