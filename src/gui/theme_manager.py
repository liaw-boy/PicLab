"""
ThemeManager — singleton QObject that broadcasts theme changes to all widgets.

Usage:
    tm = ThemeManager.instance()
    tm.set_theme("paper")   # "dark" | "light" | "paper"
    tm.theme_changed.connect(my_widget.on_theme_change)
"""
from __future__ import annotations
from PyQt6.QtCore import QObject, pyqtSignal
import src.gui.theme as T


class ThemeManager(QObject):
    # Emits True for dark, False for light/paper
    theme_changed = pyqtSignal(bool)

    _instance: "ThemeManager | None" = None

    @classmethod
    def instance(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = ThemeManager()
        return cls._instance

    def __init__(self):
        super().__init__()
        self._theme = "dark"   # default: Aurelian Dark
        T.apply_dark()

    def set_theme(self, theme: str) -> None:
        """theme: 'dark' | 'light' | 'paper'"""
        if self._theme == theme:
            return
        self._theme = theme
        if theme == "dark":
            T.apply_dark()
        elif theme == "light":
            T.apply_light()
        else:
            T.apply_paper()
        self.theme_changed.emit(theme == "dark")

    def set_dark(self, dark: bool) -> None:
        """Legacy compatibility — toggles between dark and paper."""
        self.set_theme("dark" if dark else "paper")

    def cycle_theme(self) -> None:
        """Cycle: paper → dark → light → paper"""
        order = ["paper", "dark", "light"]
        idx = order.index(self._theme)
        self.set_theme(order[(idx + 1) % len(order)])

    @property
    def is_dark(self) -> bool:
        return self._theme == "dark"

    @property
    def current_theme(self) -> str:
        return self._theme
