"""Qt desktop bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow
from .ui.theme import Palette, ThemeMode, resolve, stylesheet

__all__ = ["apply_theme", "build_application", "resolve", "run", "system_prefers_dark"]


def system_prefers_dark(application: QApplication) -> bool:
    """Decide the system preference from the platform palette.

    Qt reports the desktop colours it was given; a window background darker
    than its text means the user is running a dark desktop.
    """

    palette = application.palette()
    window = palette.color(QPalette.ColorRole.Window)
    text = palette.color(QPalette.ColorRole.WindowText)
    return window.lightness() < text.lightness()


def apply_theme(
    application: QApplication,
    mode: ThemeMode = ThemeMode.SYSTEM,
) -> Palette:
    """Repaint the whole application from one palette."""

    palette = resolve(mode, system_prefers_dark=system_prefers_dark(application))
    application.setStyleSheet(stylesheet(palette))
    return palette


def build_application(
    mode: ThemeMode = ThemeMode.SYSTEM,
) -> tuple[QApplication, MainWindow]:
    # instance() is typed as the core application; narrow it so the widget
    # API and the theme helpers are actually reachable.
    existing = QApplication.instance()
    application = existing if isinstance(existing, QApplication) else QApplication(sys.argv)
    application.setApplicationName("Collective MindGraph")
    application.setOrganizationName("CollectiveMindGraph")
    application.setStyle("Fusion")
    apply_theme(application, mode)
    return application, MainWindow()


def run() -> int:
    application, window = build_application()
    window.show()
    return application.exec()
