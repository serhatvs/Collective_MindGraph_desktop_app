"""Qt application bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .services import CollectiveMindGraphService
from .ui.main_window import MainWindow


APP_STYLESHEET = """
QWidget {
    background: #f3f6fb;
    color: #1f2933;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QMainWindow, QMenuBar, QMenu, QStatusBar {
    background: #f3f6fb;
}
QMenuBar {
    border-bottom: 1px solid #d7e0ea;
}
QMenuBar::item {
    padding: 6px 10px;
    background: transparent;
}
QMenuBar::item:selected {
    background: #dde7f2;
    border-radius: 6px;
}
QMenu {
    border: 1px solid #cfdae5;
    padding: 6px;
}
QMenu::item {
    padding: 7px 24px 7px 10px;
    border-radius: 6px;
}
QMenu::item:selected {
    background: #dde7f2;
}
QFrame#CardWidget, QFrame#SummaryBar {
    background: #ffffff;
    border: 1px solid #d6dfe8;
    border-radius: 14px;
}
QFrame#MetricPill {
    background: #f8fbff;
    border: 1px solid #d7e5f0;
    border-radius: 12px;
}
QLabel#MetricValue {
    font-size: 18px;
    font-weight: 700;
}
QLabel#SectionTitle {
    font-size: 12pt;
    font-weight: 700;
}
QLineEdit, QListWidget, QTreeWidget, QTableWidget, QComboBox, QPlainTextEdit {
    background: #ffffff;
    border: 1px solid #ccd8e4;
    border-radius: 10px;
    padding: 6px 8px;
}
QLineEdit:focus, QListWidget:focus, QTreeWidget:focus, QTableWidget:focus, QComboBox:focus, QPlainTextEdit:focus {
    border: 1px solid #4b6cb7;
}
QLabel#MutedText {
    color: #5a6b7d;
}
QLabel#VoiceStatusBadge {
    border-radius: 999px;
    padding: 5px 12px;
    font-size: 9pt;
    font-weight: 700;
}
QLabel#VoiceStatusBadge[stage="idle"] {
    background: #eef3f9;
    color: #264a7f;
    border: 1px solid #c8d6e4;
}
QLabel#VoiceStatusBadge[stage="recording"] {
    background: #fff0f0;
    color: #a13232;
    border: 1px solid #efb3b3;
}
QLabel#VoiceStatusBadge[stage="audio_ready"] {
    background: #fff7e3;
    color: #8b5a08;
    border: 1px solid #eed49a;
}
QLabel#VoiceStatusBadge[stage="transcript_ready"] {
    background: #ebfaf1;
    color: #19693d;
    border: 1px solid #b8e3c8;
}
QLabel#VoiceStatusBadge[stage="error"] {
    background: #fff0f0;
    color: #9a2121;
    border: 1px solid #efb3b3;
}
QListWidget::item, QTreeWidget::item {
    padding: 6px;
}
QListWidget::item:selected, QTreeWidget::item:selected, QTableWidget::item:selected {
    background: #dce8ff;
    color: #102036;
}
QPushButton {
    background: #264a7f;
    color: #ffffff;
    border: none;
    border-radius: 10px;
    padding: 8px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background: #1f3e6c;
}
QPushButton:disabled {
    background: #9bb0c7;
}
QPushButton[secondary="true"] {
    background: #eef3f9;
    color: #264a7f;
    border: 1px solid #c8d6e4;
}
QPushButton[secondary="true"]:hover {
    background: #e3edf8;
}
QScrollArea {
    border: none;
}
QHeaderView::section {
    background: #eef3f9;
    border: none;
    border-bottom: 1px solid #d7e0ea;
    padding: 6px;
    font-weight: 600;
}
QSplitter::handle {
    background: #dce4ed;
    width: 6px;
}
"""


def build_application() -> tuple[QApplication, MainWindow]:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Collective MindGraph")
    app.setOrganizationName("Collective MindGraph")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)
    service = CollectiveMindGraphService()
    window = MainWindow(service)
    return app, window


def run() -> int:
    app, window = build_application()
    window.show()
    return app.exec()
