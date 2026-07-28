"""Qt desktop bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .ui.design_tokens import application_stylesheet
from .ui.main_window import MainWindow


def build_application() -> tuple[QApplication, MainWindow]:
    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName("Collective MindGraph")
    application.setOrganizationName("CollectiveMindGraph")
    application.setStyle("Fusion")
    application.setStyleSheet(application_stylesheet())
    return application, MainWindow()


def run() -> int:
    application, window = build_application()
    window.show()
    return application.exec()
