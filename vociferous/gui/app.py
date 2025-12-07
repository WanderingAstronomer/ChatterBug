"""Main KivyMD application for Vociferous GUI."""

from __future__ import annotations

from pathlib import Path

from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition
from kivymd.app import MDApp
from kivymd.uix.navigationdrawer import MDNavigationLayout, MDNavigationDrawer
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.list import OneLineIconListItem, IconLeftWidget
from kivymd.uix.boxlayout import MDBoxLayout

import structlog

from .splash import SplashScreen
from .screens import HomeScreen, SettingsScreen
from .installer import InstallMode

logger = structlog.get_logger(__name__)


class VociferousGUIApp(MDApp):
    """Main KivyMD application for Vociferous."""

    def __init__(self, **kwargs):
        """Initialize the Vociferous application."""
        super().__init__(**kwargs)
        self.title = "Vociferous - AI Transcription"
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.primary_hue = "700"
        self.theme_cls.accent_palette = "LightBlue"
        self.theme_cls.accent_hue = "400"
        
        # Window configuration
        Window.size = (1200, 800)
        Window.minimum_width = 800
        Window.minimum_height = 600
        
        self.screen_manager: ScreenManager | None = None
        self.nav_drawer: MDNavigationDrawer | None = None

    def build(self) -> MDNavigationLayout | ScreenManager:
        """Build the application UI.
        
        Returns:
            The root widget (navigation layout or screen manager for splash).
        """
        logger.info("Building Vociferous application")
        
        # Check if first run
        marker_file = Path.home() / ".config" / "vociferous" / ".gui_setup_complete"
        is_first_run = not marker_file.exists()
        
        if is_first_run:
            # Show splash screen first
            return self._build_splash()
        else:
            # Go directly to main app
            return self._build_main_app()

    def _build_splash(self) -> ScreenManager:
        """Build splash screen for first run.
        
        Returns:
            Screen manager with splash screen.
        """
        screen_manager = ScreenManager(transition=NoTransition())
        splash = SplashScreen(on_complete=self._on_splash_complete)
        screen_manager.add_widget(splash)
        self.screen_manager = screen_manager
        return screen_manager

    def _on_splash_complete(self, mode: InstallMode | None) -> None:
        """Handle splash screen completion.
        
        Args:
            mode: Selected installation mode, or None if skipped
        """
        logger.info("Splash complete, loading main app", mode=mode)
        
        # Replace root with main app
        self.root.clear_widgets()
        main_app = self._build_main_app()
        self.root.add_widget(main_app)

    def _build_main_app(self) -> MDNavigationLayout:
        """Build the main application UI with navigation.
        
        Returns:
            Navigation layout with drawer.
        """
        # Main layout
        nav_layout = MDNavigationLayout()
        
        # Screen manager for main content
        self.screen_manager = ScreenManager()
        
        # Add screens
        self.screen_manager.add_widget(HomeScreen(name="home"))
        self.screen_manager.add_widget(SettingsScreen(name="settings"))
        
        # Content layout with toolbar
        content_layout = MDBoxLayout(orientation="vertical")
        
        # Top app bar
        toolbar = MDTopAppBar(
            title="Vociferous",
            left_action_items=[["menu", lambda x: self._toggle_nav_drawer()]],
        )
        content_layout.add_widget(toolbar)
        
        # Add screen manager to content
        content_layout.add_widget(self.screen_manager)
        
        # Navigation drawer
        self.nav_drawer = MDNavigationDrawer()
        nav_drawer_content = MDBoxLayout(orientation="vertical", padding=20, spacing=10)
        
        # Navigation items
        nav_items = [
            ("home", "Home"),
            ("cog", "Settings"),
        ]
        
        for icon, text in nav_items:
            item = OneLineIconListItem(
                text=text,
                on_release=lambda x, name=text.lower(): self._navigate_to(name)
            )
            item.add_widget(IconLeftWidget(icon=icon))
            nav_drawer_content.add_widget(item)
        
        self.nav_drawer.add_widget(nav_drawer_content)
        
        # Add to nav layout
        nav_layout.add_widget(content_layout)
        nav_layout.add_widget(self.nav_drawer)
        
        return nav_layout

    def _toggle_nav_drawer(self) -> None:
        """Toggle the navigation drawer."""
        if self.nav_drawer:
            if self.nav_drawer.state == "open":
                self.nav_drawer.set_state("close")
            else:
                self.nav_drawer.set_state("open")

    def _navigate_to(self, screen_name: str) -> None:
        """Navigate to a specific screen.
        
        Args:
            screen_name: Name of the screen to navigate to
        """
        logger.info("Navigating to screen", screen=screen_name)
        if self.screen_manager:
            self.screen_manager.current = screen_name
        if self.nav_drawer:
            self.nav_drawer.set_state("close")


def run_gui() -> None:
    """Run the Vociferous GUI application."""
    app = VociferousGUIApp()
    app.run()
