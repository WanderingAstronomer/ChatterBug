"""Animation utilities for Vociferous GUI.

Provides:
- Screen transition animations
- Loading spinners
- Progress animations
- Fade effects
- Pulse effects for active states
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import BooleanProperty, NumericProperty
from kivy.uix.widget import Widget
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.spinner import MDSpinner


class FadeTransition:
    """Utility for fading widgets in and out."""
    
    @staticmethod
    def fade_in(widget: Widget, duration: float = 0.3, on_complete: Callable | None = None) -> Animation:
        """Fade a widget in from transparent to opaque.
        
        Args:
            widget: Widget to animate
            duration: Animation duration in seconds
            on_complete: Callback when animation completes
        
        Returns:
            The Animation instance
        """
        widget.opacity = 0
        anim = Animation(opacity=1, duration=duration, t='out_cubic')
        
        if on_complete:
            anim.bind(on_complete=lambda *x: on_complete())
        
        anim.start(widget)
        return anim
    
    @staticmethod
    def fade_out(widget: Widget, duration: float = 0.3, on_complete: Callable | None = None) -> Animation:
        """Fade a widget out from opaque to transparent.
        
        Args:
            widget: Widget to animate
            duration: Animation duration in seconds
            on_complete: Callback when animation completes
        
        Returns:
            The Animation instance
        """
        anim = Animation(opacity=0, duration=duration, t='in_cubic')
        
        if on_complete:
            anim.bind(on_complete=lambda *x: on_complete())
        
        anim.start(widget)
        return anim
    
    @staticmethod
    def crossfade(widget_out: Widget, widget_in: Widget, duration: float = 0.3) -> None:
        """Crossfade between two widgets.
        
        Args:
            widget_out: Widget to fade out
            widget_in: Widget to fade in
            duration: Animation duration in seconds
        """
        FadeTransition.fade_out(widget_out, duration)
        FadeTransition.fade_in(widget_in, duration)


class PulseAnimation:
    """Utility for pulsing effects on widgets."""
    
    @staticmethod
    def start(widget: Widget, min_opacity: float = 0.5, duration: float = 1.0) -> Animation:
        """Start a pulsing animation on a widget.
        
        Args:
            widget: Widget to animate
            min_opacity: Minimum opacity during pulse
            duration: Duration of one pulse cycle
        
        Returns:
            The Animation instance (already started)
        """
        anim = (
            Animation(opacity=min_opacity, duration=duration / 2, t='in_out_sine') +
            Animation(opacity=1, duration=duration / 2, t='in_out_sine')
        )
        anim.repeat = True
        anim.start(widget)
        return anim
    
    @staticmethod
    def stop(widget: Widget) -> None:
        """Stop any animations on a widget and reset opacity.
        
        Args:
            widget: Widget to stop animating
        """
        Animation.stop_all(widget)
        widget.opacity = 1


class SlideAnimation:
    """Utility for sliding widgets in and out."""
    
    @staticmethod
    def slide_in_from_right(widget: Widget, duration: float = 0.3, distance: float = 100) -> Animation:
        """Slide a widget in from the right.
        
        Args:
            widget: Widget to animate
            duration: Animation duration in seconds
            distance: Slide distance in dp
        
        Returns:
            The Animation instance
        """
        original_x = widget.x
        widget.x = widget.x + dp(distance)
        widget.opacity = 0
        
        anim = Animation(x=original_x, opacity=1, duration=duration, t='out_cubic')
        anim.start(widget)
        return anim
    
    @staticmethod
    def slide_in_from_left(widget: Widget, duration: float = 0.3, distance: float = 100) -> Animation:
        """Slide a widget in from the left.
        
        Args:
            widget: Widget to animate
            duration: Animation duration in seconds
            distance: Slide distance in dp
        
        Returns:
            The Animation instance
        """
        original_x = widget.x
        widget.x = widget.x - dp(distance)
        widget.opacity = 0
        
        anim = Animation(x=original_x, opacity=1, duration=duration, t='out_cubic')
        anim.start(widget)
        return anim
    
    @staticmethod
    def slide_in_from_bottom(widget: Widget, duration: float = 0.3, distance: float = 50) -> Animation:
        """Slide a widget in from the bottom.
        
        Args:
            widget: Widget to animate
            duration: Animation duration in seconds
            distance: Slide distance in dp
        
        Returns:
            The Animation instance
        """
        original_y = widget.y
        widget.y = widget.y - dp(distance)
        widget.opacity = 0
        
        anim = Animation(y=original_y, opacity=1, duration=duration, t='out_cubic')
        anim.start(widget)
        return anim


class LoadingSpinner(MDBoxLayout):
    """A loading spinner with optional text.
    
    Shows a centered spinner with message below.
    """
    
    is_active = BooleanProperty(False)
    
    def __init__(
        self,
        message: str = "Loading...",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.size_hint = (None, None)
        self.size = (dp(120), dp(100))
        self.pos_hint = {"center_x": 0.5, "center_y": 0.5}
        self.spacing = dp(12)
        
        self.spinner = MDSpinner(
            size_hint=(None, None),
            size=(dp(48), dp(48)),
            pos_hint={"center_x": 0.5},
            active=False,
        )
        self.add_widget(self.spinner)
        
        self.message_label = MDLabel(
            text=message,
            font_style="Caption",
            theme_text_color="Secondary",
            halign="center",
            size_hint=(1, None),
            height=dp(24),
        )
        self.add_widget(self.message_label)
        
        self.bind(is_active=self._on_active_change)
    
    def _on_active_change(self, instance: Any, value: bool) -> None:
        """Handle active state changes."""
        self.spinner.active = value
        if value:
            FadeTransition.fade_in(self, duration=0.2)
        else:
            FadeTransition.fade_out(self, duration=0.2)
    
    def set_message(self, message: str) -> None:
        """Update the loading message.
        
        Args:
            message: New message to display
        """
        self.message_label.text = message


class AnimatedProgressBar(MDProgressBar):
    """Progress bar with smooth animations.
    
    Animates value changes smoothly instead of jumping.
    """
    
    target_value = NumericProperty(0)
    
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._animation: Animation | None = None
        self.bind(target_value=self._animate_to_target)
    
    def _animate_to_target(self, instance: Any, value: float) -> None:
        """Animate to the target value.
        
        Args:
            instance: Widget instance
            value: Target value
        """
        # Stop any existing animation
        if self._animation:
            self._animation.cancel(self)
        
        # Calculate duration based on distance
        distance = abs(value - self.value)
        duration = min(0.5, max(0.1, distance / 50))
        
        self._animation = Animation(value=value, duration=duration, t='out_quad')
        self._animation.start(self)
    
    def set_progress(self, value: float, animate: bool = True) -> None:
        """Set progress value with optional animation.
        
        Args:
            value: Progress value (0-100)
            animate: Whether to animate the change
        """
        if animate:
            self.target_value = value
        else:
            if self._animation:
                self._animation.cancel(self)
            self.value = value


class SuccessAnimation:
    """Success check animation for completed operations."""
    
    @staticmethod
    def play(widget: Widget, on_complete: Callable | None = None) -> None:
        """Play a success animation (scale up then back).
        
        Args:
            widget: Widget to animate
            on_complete: Callback when animation completes
        """
        # Scale up
        anim = (
            Animation(scale=1.2, duration=0.15, t='out_back') +
            Animation(scale=1.0, duration=0.1, t='in_out_sine')
        )
        
        if on_complete:
            anim.bind(on_complete=lambda *x: on_complete())
        
        anim.start(widget)


class ShakeAnimation:
    """Shake animation for error feedback."""
    
    @staticmethod
    def play(widget: Widget, intensity: float = 10, on_complete: Callable | None = None) -> None:
        """Play a shake animation (horizontal).
        
        Args:
            widget: Widget to animate
            intensity: Shake distance in dp
            on_complete: Callback when animation completes
        """
        original_x = widget.x
        
        anim = (
            Animation(x=original_x - dp(intensity), duration=0.05) +
            Animation(x=original_x + dp(intensity), duration=0.05) +
            Animation(x=original_x - dp(intensity * 0.5), duration=0.05) +
            Animation(x=original_x + dp(intensity * 0.5), duration=0.05) +
            Animation(x=original_x, duration=0.05)
        )
        
        if on_complete:
            anim.bind(on_complete=lambda *x: on_complete())
        
        anim.start(widget)


class StaggeredAnimation:
    """Utility for staggered animations on multiple widgets."""
    
    @staticmethod
    def fade_in_sequence(
        widgets: list[Widget],
        delay: float = 0.1,
        duration: float = 0.3,
    ) -> None:
        """Fade in widgets in sequence with delay.
        
        Args:
            widgets: List of widgets to animate
            delay: Delay between each widget
            duration: Duration of each fade
        """
        for i, widget in enumerate(widgets):
            widget.opacity = 0
            Clock.schedule_once(
                lambda dt, w=widget: FadeTransition.fade_in(w, duration),
                i * delay
            )
    
    @staticmethod
    def slide_in_sequence(
        widgets: list[Widget],
        direction: str = "bottom",
        delay: float = 0.1,
        duration: float = 0.3,
    ) -> None:
        """Slide in widgets in sequence with delay.
        
        Args:
            widgets: List of widgets to animate
            direction: Direction to slide from ("left", "right", "bottom")
            delay: Delay between each widget
            duration: Duration of each slide
        """
        slide_funcs = {
            "left": SlideAnimation.slide_in_from_left,
            "right": SlideAnimation.slide_in_from_right,
            "bottom": SlideAnimation.slide_in_from_bottom,
        }
        
        slide_func = slide_funcs.get(direction, SlideAnimation.slide_in_from_bottom)
        
        for i, widget in enumerate(widgets):
            widget.opacity = 0
            Clock.schedule_once(
                lambda dt, w=widget: slide_func(w, duration),
                i * delay
            )


def animate_screen_transition(
    screen_out: Widget,
    screen_in: Widget,
    direction: str = "left",
    duration: float = 0.3,
) -> None:
    """Animate transition between screens.
    
    Args:
        screen_out: Screen to animate out
        screen_in: Screen to animate in
        direction: Direction ("left" or "right")
        duration: Animation duration
    """
    if direction == "left":
        # Screen out slides left, screen in slides from right
        Animation(opacity=0, duration=duration).start(screen_out)
        SlideAnimation.slide_in_from_right(screen_in, duration)
    else:
        # Screen out slides right, screen in slides from left
        Animation(opacity=0, duration=duration).start(screen_out)
        SlideAnimation.slide_in_from_left(screen_in, duration)
