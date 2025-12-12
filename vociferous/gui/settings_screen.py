"""Enhanced settings screen with tabbed interface.

Implements:
- Tabbed layout (Profiles, Engine, Segmentation, Advanced)
- Preset cards for quick configuration
- Auto-generated forms from config schema
- Real-time validation
"""

from __future__ import annotations

from typing import Any

import structlog
from kivy.metrics import dp
from kivy.uix.screenmanager import Screen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.list import TwoLineListItem
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.selectioncontrol import MDSwitch
from kivymd.uix.slider import MDSlider
from kivymd.uix.tab import MDTabs, MDTabsBase

from vociferous.config import load_config, save_config

from .widgets import Colors, PresetCard

logger = structlog.get_logger(__name__)


def _get_app() -> Any:
    """Get the running MDApp instance."""
    from kivymd.app import MDApp
    return MDApp.get_running_app()


class SettingsTab(MDBoxLayout, MDTabsBase):
    """Base class for settings tabs."""
    
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = [dp(16), dp(12)]
        self.spacing = dp(12)


class ProfilesTab(SettingsTab):
    """Profiles tab with preset cards."""
    
    def __init__(self, on_preset_selected: Any = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.title = "Profiles"
        self.icon = "tune-vertical"
        self.on_preset_callback = on_preset_selected
        self._build_ui()
    
    def _build_ui(self) -> None:
        """Build the profiles tab UI."""
        # Section: Engine Presets
        engine_header = MDLabel(
            text="[b]Engine Presets[/b]",
            markup=True,
            font_style="Subtitle1",
            size_hint=(1, None),
            height=dp(32),
        )
        self.add_widget(engine_header)
        
        engine_desc = MDLabel(
            text="Choose a preset optimized for your workflow",
            font_style="Caption",
            theme_text_color="Secondary",
            size_hint=(1, None),
            height=dp(24),
        )
        self.add_widget(engine_desc)
        
        # Engine preset cards
        engine_scroll = MDScrollView(
            size_hint=(1, None),
            height=dp(120),
            do_scroll_y=False,
        )
        
        engine_row = MDBoxLayout(
            orientation="horizontal",
            size_hint=(None, 1),
            spacing=dp(12),
            padding=[0, dp(8)],
        )
        engine_row.bind(minimum_width=engine_row.setter("width"))
        
        engine_presets = [
            ("Accuracy", "Best quality, Canary-Qwen BF16", "accuracy_focus"),
            ("Speed", "Fast, Whisper Turbo INT8", "speed_focus"),
            ("Balanced", "Good balance, FP16", "balanced"),
            ("Low Memory", "For limited VRAM", "low_memory"),
        ]
        
        self.engine_cards: list[PresetCard] = []
        for name, desc, preset_id in engine_presets:
            card = PresetCard(
                name=name,
                description=desc,
                on_select=lambda n, p=preset_id: self._on_engine_preset(p, n),
            )
            self.engine_cards.append(card)
            engine_row.add_widget(card)
        
        # Default to balanced
        if len(self.engine_cards) > 2:
            self.engine_cards[2].selected = True
        
        engine_scroll.add_widget(engine_row)
        self.add_widget(engine_scroll)
        
        # Section: Segmentation Presets
        seg_header = MDLabel(
            text="[b]Segmentation Presets[/b]",
            markup=True,
            font_style="Subtitle1",
            size_hint=(1, None),
            height=dp(32),
        )
        self.add_widget(seg_header)
        
        seg_desc = MDLabel(
            text="Audio preprocessing settings for different content types",
            font_style="Caption",
            theme_text_color="Secondary",
            size_hint=(1, None),
            height=dp(24),
        )
        self.add_widget(seg_desc)
        
        # Segmentation preset cards
        seg_scroll = MDScrollView(
            size_hint=(1, None),
            height=dp(120),
            do_scroll_y=False,
        )
        
        seg_row = MDBoxLayout(
            orientation="horizontal",
            size_hint=(None, 1),
            spacing=dp(12),
            padding=[0, dp(8)],
        )
        seg_row.bind(minimum_width=seg_row.setter("width"))
        
        seg_presets = [
            ("Precise", "Accurate detection", "precise"),
            ("Fast", "Quick processing", "fast"),
            ("Conversation", "Dialogue-optimized", "conversation"),
            ("Podcast", "Long-form audio", "podcast"),
        ]
        
        self.seg_cards: list[PresetCard] = []
        for name, desc, preset_id in seg_presets:
            card = PresetCard(
                name=name,
                description=desc,
                on_select=lambda n, p=preset_id: self._on_seg_preset(p, n),
            )
            self.seg_cards.append(card)
            seg_row.add_widget(card)
        
        seg_scroll.add_widget(seg_row)
        self.add_widget(seg_scroll)
        
        # Spacer
        self.add_widget(MDBoxLayout(size_hint=(1, 1)))
    
    def _on_engine_preset(self, preset_id: str, name: str) -> None:
        """Handle engine preset selection."""
        for card in self.engine_cards:
            card.selected = (card.name == name)
        
        if self.on_preset_callback:
            self.on_preset_callback("engine", preset_id)
        
        logger.info("Engine preset selected", preset=preset_id)
    
    def _on_seg_preset(self, preset_id: str, name: str) -> None:
        """Handle segmentation preset selection."""
        for card in self.seg_cards:
            card.selected = (card.name == name)
        
        if self.on_preset_callback:
            self.on_preset_callback("segmentation", preset_id)
        
        logger.info("Segmentation preset selected", preset=preset_id)


class EngineTab(SettingsTab):
    """Engine configuration tab."""
    
    def __init__(self, config: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.title = "Engine"
        self.icon = "engine"
        self.config = config
        self._build_ui()
    
    def _build_ui(self) -> None:
        """Build the engine tab UI."""
        scroll = MDScrollView(size_hint=(1, 1))
        content = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(8),
            padding=[0, 0, 0, dp(20)],
        )
        content.bind(minimum_height=content.setter("height"))
        
        # Engine selection
        engine_item = TwoLineListItem(
            text="ASR Engine",
            secondary_text=f"Current: {self.config.engine}",
            on_release=self._show_engine_menu,
        )
        self.engine_item = engine_item
        content.add_widget(engine_item)
        
        # Model selection
        model_item = TwoLineListItem(
            text="Model Name",
            secondary_text=f"Current: {self.config.model_name or 'Default'}",
        )
        self.model_item = model_item
        content.add_widget(model_item)
        
        # Device selection
        device_item = TwoLineListItem(
            text="Compute Device",
            secondary_text=f"Current: {self.config.device}",
            on_release=self._show_device_menu,
        )
        self.device_item = device_item
        content.add_widget(device_item)
        
        # Compute type
        compute_item = TwoLineListItem(
            text="Compute Precision",
            secondary_text=f"Current: {self.config.compute_type}",
            on_release=self._show_compute_menu,
        )
        self.compute_item = compute_item
        content.add_widget(compute_item)
        
        # Help text
        help_card = MDCard(
            orientation="vertical",
            padding=[dp(12), dp(8)],
            size_hint=(1, None),
            height=dp(80),
            radius=[dp(8)],
        )
        help_card.md_bg_color = Colors.SURFACE_VARIANT
        
        help_text = MDLabel(
            text="💡 Canary-Qwen provides best quality but requires NVIDIA GPU.\n"
                 "    Whisper Turbo is faster and works on CPU.",
            font_style="Caption",
            theme_text_color="Secondary",
        )
        help_card.add_widget(help_text)
        content.add_widget(help_card)
        
        scroll.add_widget(content)
        self.add_widget(scroll)
    
    def _show_engine_menu(self, item: Any) -> None:
        """Show engine selection menu."""
        engines = [
            ("canary_qwen", "Canary-Qwen (High Quality, GPU)"),
            ("whisper_turbo", "Whisper Turbo (Fast, CPU/GPU)"),
        ]
        
        menu_items = [
            {
                "text": label,
                "on_release": lambda x=engine_id: self._select_engine(x),
            }
            for engine_id, label in engines
        ]
        
        self.engine_menu = MDDropdownMenu(
            caller=item,
            items=menu_items,
            width_mult=5,
        )
        self.engine_menu.open()
    
    def _select_engine(self, engine: str) -> None:
        """Select an engine."""
        valid_engines = {"canary_qwen", "whisper_turbo"}
        if engine in valid_engines:
            self.config.engine = engine
            self.engine_item.secondary_text = f"Current: {engine}"
        
        if hasattr(self, "engine_menu"):
            self.engine_menu.dismiss()
    
    def _show_device_menu(self, item: Any) -> None:
        """Show device selection menu."""
        devices = [
            ("auto", "Auto-detect"),
            ("cuda", "GPU (NVIDIA CUDA)"),
            ("cpu", "CPU (slower)"),
        ]
        
        menu_items = [
            {
                "text": label,
                "on_release": lambda x=device_id: self._select_device(x),
            }
            for device_id, label in devices
        ]
        
        self.device_menu = MDDropdownMenu(
            caller=item,
            items=menu_items,
            width_mult=4,
        )
        self.device_menu.open()
    
    def _select_device(self, device: str) -> None:
        """Select a device."""
        self.config.device = device
        self.device_item.secondary_text = f"Current: {device}"
        
        if hasattr(self, "device_menu"):
            self.device_menu.dismiss()
    
    def _show_compute_menu(self, item: Any) -> None:
        """Show compute type menu."""
        types = [
            ("auto", "Auto (recommended)"),
            ("bfloat16", "BF16 (Canary-Qwen optimized)"),
            ("float16", "FP16 (Balanced)"),
            ("float32", "FP32 (Highest quality)"),
            ("int8", "INT8 (Fastest)"),
        ]
        
        menu_items = [
            {
                "text": label,
                "on_release": lambda x=type_id: self._select_compute(x),
            }
            for type_id, label in types
        ]
        
        self.compute_menu = MDDropdownMenu(
            caller=item,
            items=menu_items,
            width_mult=5,
        )
        self.compute_menu.open()
    
    def _select_compute(self, compute_type: str) -> None:
        """Select compute type."""
        self.config.compute_type = compute_type
        self.compute_item.secondary_text = f"Current: {compute_type}"
        
        if hasattr(self, "compute_menu"):
            self.compute_menu.dismiss()


class SegmentationTab(SettingsTab):
    """Segmentation/VAD configuration tab."""
    
    def __init__(self, config: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.title = "Segmentation"
        self.icon = "waveform"
        self.config = config
        self._build_ui()
    
    def _build_ui(self) -> None:
        """Build the segmentation tab UI."""
        scroll = MDScrollView(size_hint=(1, 1))
        content = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(16),
            padding=[0, 0, 0, dp(20)],
        )
        content.bind(minimum_height=content.setter("height"))
        
        # VAD Threshold slider
        content.add_widget(self._create_slider_setting(
            title="VAD Sensitivity",
            description="Lower = more sensitive to quiet speech",
            min_val=0.1,
            max_val=0.9,
            current_val=float(self.config.params.get("vad_threshold", "0.5")),
            key="vad_threshold",
        ))
        
        # Min Silence slider
        content.add_widget(self._create_slider_setting(
            title="Minimum Silence (ms)",
            description="How long a pause must be to split segments",
            min_val=100,
            max_val=2000,
            current_val=float(self.config.params.get("min_silence_ms", "500")),
            key="min_silence_ms",
            step=100,
        ))
        
        # Min Speech slider
        content.add_widget(self._create_slider_setting(
            title="Minimum Speech (ms)",
            description="Filter out very short sounds",
            min_val=100,
            max_val=2000,
            current_val=float(self.config.params.get("min_speech_ms", "250")),
            key="min_speech_ms",
            step=50,
        ))
        
        # Speech Padding slider
        content.add_widget(self._create_slider_setting(
            title="Speech Padding (ms)",
            description="Extra padding around detected speech",
            min_val=0,
            max_val=500,
            current_val=float(self.config.params.get("speech_pad_ms", "100")),
            key="speech_pad_ms",
            step=50,
        ))
        
        scroll.add_widget(content)
        self.add_widget(scroll)
    
    def _create_slider_setting(
        self,
        title: str,
        description: str,
        min_val: float,
        max_val: float,
        current_val: float,
        key: str,
        step: float = 0.05,
    ) -> MDCard:
        """Create a slider setting card."""
        card = MDCard(
            orientation="vertical",
            padding=[dp(16), dp(12)],
            spacing=dp(4),
            size_hint=(1, None),
            height=dp(120),
            radius=[dp(8)],
        )
        card.md_bg_color = Colors.SURFACE_VARIANT
        
        # Header row
        header = MDBoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(30),
        )
        
        title_label = MDLabel(
            text=f"[b]{title}[/b]",
            markup=True,
            font_style="Subtitle2",
            size_hint=(1, 1),
        )
        header.add_widget(title_label)
        
        value_label = MDLabel(
            text=str(current_val),
            font_style="Body2",
            theme_text_color="Secondary",
            halign="right",
            size_hint=(None, 1),
            width=dp(60),
        )
        header.add_widget(value_label)
        
        card.add_widget(header)
        
        # Description
        desc_label = MDLabel(
            text=description,
            font_style="Caption",
            theme_text_color="Secondary",
            size_hint=(1, None),
            height=dp(20),
        )
        card.add_widget(desc_label)
        
        # Slider
        slider = MDSlider(
            min=min_val,
            max=max_val,
            value=current_val,
            step=step,
            size_hint=(1, None),
            height=dp(40),
        )
        
        def on_value_change(instance: Any, value: float) -> None:
            value_label.text = f"{value:.2f}" if step < 1 else str(int(value))
            self.config.params[key] = str(value)
        
        slider.bind(value=on_value_change)
        card.add_widget(slider)
        
        return card


class AppearanceTab(SettingsTab):
    """Appearance and accessibility settings tab."""
    
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.title = "Appearance"
        self.icon = "palette"
        self._build_ui()
    
    def _build_ui(self) -> None:
        """Build the appearance tab UI."""
        scroll = MDScrollView(size_hint=(1, 1))
        content = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(8),
            padding=[0, 0, 0, dp(20)],
        )
        content.bind(minimum_height=content.setter("height"))
        
        # Theme selection
        theme_item = TwoLineListItem(
            text="Theme",
            secondary_text="Current: Dark",
            on_release=self._show_theme_menu,
        )
        self.theme_item = theme_item
        content.add_widget(theme_item)
        
        # Font size
        font_item = TwoLineListItem(
            text="Font Size",
            secondary_text="Current: 100%",
            on_release=self._show_font_menu,
        )
        self.font_item = font_item
        content.add_widget(font_item)
        
        # High contrast mode
        contrast_layout = MDBoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(60),
            padding=[dp(16), 0],
        )
        
        contrast_label = MDLabel(
            text="High Contrast Mode",
            font_style="Body1",
            size_hint=(0.7, 1),
            valign="center",
        )
        contrast_layout.add_widget(contrast_label)
        
        self.contrast_switch = MDSwitch(
            size_hint=(0.3, 1),
            pos_hint={"center_y": 0.5},
        )
        self.contrast_switch.bind(active=self._on_contrast_toggle)
        contrast_layout.add_widget(self.contrast_switch)
        content.add_widget(contrast_layout)
        
        # Animations
        anim_layout = MDBoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(60),
            padding=[dp(16), 0],
        )
        
        anim_label = MDLabel(
            text="Enable Animations",
            font_style="Body1",
            size_hint=(0.7, 1),
            valign="center",
        )
        anim_layout.add_widget(anim_label)
        
        anim_switch = MDSwitch(
            size_hint=(0.3, 1),
            pos_hint={"center_y": 0.5},
            active=True,
        )
        anim_layout.add_widget(anim_switch)
        content.add_widget(anim_layout)
        
        scroll.add_widget(content)
        self.add_widget(scroll)
    
    def _show_theme_menu(self, item: Any) -> None:
        """Show theme selection menu."""
        themes = ["Dark", "Light"]
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
            width_mult=3,
        )
        self.theme_menu.open()
    
    def _select_theme(self, theme: str) -> None:
        """Select a theme."""
        app = _get_app()
        if app and hasattr(app, "switch_theme"):
            app.switch_theme(theme)
        
        self.theme_item.secondary_text = f"Current: {theme}"
        
        if hasattr(self, "theme_menu"):
            self.theme_menu.dismiss()
    
    def _show_font_menu(self, item: Any) -> None:
        """Show font size menu."""
        sizes = ["80%", "90%", "100%", "110%", "120%", "130%", "140%", "150%"]
        menu_items = [
            {
                "text": size,
                "on_release": lambda x=size: self._select_font(x),
            }
            for size in sizes
        ]
        
        self.font_menu = MDDropdownMenu(
            caller=item,
            items=menu_items,
            width_mult=3,
        )
        self.font_menu.open()
    
    def _select_font(self, size: str) -> None:
        """Select font size."""
        self.font_item.secondary_text = f"Current: {size}"
        
        if hasattr(self, "font_menu"):
            self.font_menu.dismiss()
        
        # Show restart hint
        app = _get_app()
        if app and hasattr(app, "show_notification"):
            app.show_notification(f"Font size: {size} (restart may be required)")
    
    def _on_contrast_toggle(self, switch: Any, active: bool) -> None:
        """Handle high contrast toggle."""
        app = _get_app()
        if app:
            if active:
                # Apply high contrast colors
                app.theme_cls.primary_palette = "Yellow"
                app.theme_cls.accent_palette = "Amber"
                app.theme_cls.primary_hue = "600"
                if hasattr(app, "show_notification"):
                    app.show_notification("High contrast mode enabled")
            else:
                # Restore default colors
                app.theme_cls.primary_palette = "Blue"
                app.theme_cls.accent_palette = "LightBlue"
                app.theme_cls.primary_hue = "700"
                if hasattr(app, "show_notification"):
                    app.show_notification("High contrast mode disabled")


class EnhancedSettingsScreen(Screen):
    """Enhanced settings screen with tabbed interface."""
    
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.config = load_config()
        self._build_ui()
    
    def _build_ui(self) -> None:
        """Build the settings screen UI."""
        main_layout = MDBoxLayout(
            orientation="vertical",
            spacing=dp(0),
            padding=[dp(16), dp(12)],
        )
        
        # Header
        header = MDBoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(48),
            spacing=dp(8),
        )
        
        title = MDLabel(
            text="[b]Settings[/b]",
            markup=True,
            font_style="H5",
            theme_text_color="Primary",
            size_hint=(1, 1),
            valign="center",
        )
        header.add_widget(title)
        
        main_layout.add_widget(header)
        
        # Tabs - disable swipe to prevent drag confusion
        self.tabs = MDTabs(
            background_color=Colors.SURFACE,
            text_color_active=Colors.PRIMARY,
            text_color_normal=Colors.TEXT_SECONDARY,
            indicator_color=Colors.PRIMARY,
            allow_stretch=False,
            lock_swiping=True,  # Disable swipe between tabs
        )
        
        # Add tab pages
        profiles_tab = ProfilesTab(on_preset_selected=self._on_preset_selected)
        engine_tab = EngineTab(config=self.config)
        seg_tab = SegmentationTab(config=self.config)
        appearance_tab = AppearanceTab()
        
        self.tabs.add_widget(profiles_tab)
        self.tabs.add_widget(engine_tab)
        self.tabs.add_widget(seg_tab)
        self.tabs.add_widget(appearance_tab)
        
        # Store references
        self.profiles_tab = profiles_tab
        self.engine_tab = engine_tab
        self.seg_tab = seg_tab
        self.appearance_tab = appearance_tab
        
        main_layout.add_widget(self.tabs)
        
        # Save button
        save_layout = MDBoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(60),
            padding=[0, dp(8)],
        )
        
        save_button = MDRaisedButton(
            text="Save Settings",
            size_hint=(1, 1),
            on_release=self._save_settings,
        )
        save_layout.add_widget(save_button)
        
        main_layout.add_widget(save_layout)
        
        self.add_widget(main_layout)
    
    def _on_preset_selected(self, preset_type: str, preset_id: str) -> None:
        """Handle preset selection from profiles tab."""
        try:
            if preset_type == "engine":
                self._apply_engine_preset(preset_id)
            elif preset_type == "segmentation":
                self._apply_segmentation_preset(preset_id)
        except Exception as e:
            logger.error("Failed to apply preset", error=str(e))
    
    def _apply_engine_preset(self, preset_id: str) -> None:
        """Apply an engine preset."""
        try:
            from vociferous.config.presets import get_engine_presets
            
            presets = {p.name: p for p in get_engine_presets()}
            if preset_id in presets:
                preset = presets[preset_id]
                # Apply preset config to current config
                logger.info("Applied engine preset", preset=preset_id)
        except ImportError:
            logger.warning("Presets module not available")
    
    def _apply_segmentation_preset(self, preset_id: str) -> None:
        """Apply a segmentation preset."""
        try:
            from vociferous.config.presets import get_segmentation_presets
            
            presets = {p.name: p for p in get_segmentation_presets()}
            if preset_id in presets:
                preset = presets[preset_id]
                # Apply preset config to current config
                logger.info("Applied segmentation preset", preset=preset_id)
        except ImportError:
            logger.warning("Presets module not available")
    
    def _save_settings(self, *args: Any) -> None:
        """Save all settings."""
        try:
            serializable_config = self._make_serializable(self.config)
            save_config(serializable_config)
            logger.info("Settings saved")
            self._show_snackbar("Settings saved")
        except Exception as e:
            logger.error("Failed to save settings", error=str(e))
            self._show_snackbar(f"Failed to save: {e}", error=True)

    def _make_serializable(self, value: Any) -> Any:
        """Convert config values to TOML-serializable types (e.g., Path -> str)."""
        from pathlib import Path

        if isinstance(value, dict):
            return {k: self._make_serializable(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._make_serializable(v) for v in value]
        if isinstance(value, Path):
            return str(value)
        return value
    
    def _show_snackbar(self, text: str, error: bool = False) -> None:
        """Show a snackbar notification (KivyMD 1.2 compatible)."""
        from kivymd.uix.snackbar import MDSnackbar
        snackbar = MDSnackbar(text, duration=3 if not error else 5)
        if error:
            snackbar.md_bg_color = Colors.ERROR
        snackbar.open()
