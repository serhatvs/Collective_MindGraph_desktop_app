"""Qt application bootstrap for the companion app."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .services import CollectiveMindGraphCompanionService
from .ui.main_window import MainWindow


APP_STYLESHEET = """
QWidget {
    background: #f5f7f5;
    color: #22303a;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QMainWindow, QMenuBar, QMenu, QStatusBar {
    background: #f5f7f5;
}
QMenuBar {
    border-bottom: 1px solid #d7dfdb;
}
QMenuBar::item {
    padding: 6px 10px;
    background: transparent;
}
QMenuBar::item:selected {
    background: #dfe9e2;
    border-radius: 6px;
}
QMenu {
    border: 1px solid #d4ddd8;
    padding: 6px;
}
QMenu::item {
    padding: 7px 24px 7px 10px;
    border-radius: 6px;
}
QMenu::item:selected {
    background: #e3ece6;
}
QFrame#CardWidget, QFrame#SummaryBar {
    background: #ffffff;
    border: 1px solid #d7dfdb;
    border-radius: 14px;
}
QFrame#MetricPill {
    background: #f7faf8;
    border: 1px solid #dce5e0;
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
QLineEdit, QListWidget, QTreeWidget, QTableWidget, QComboBox, QTextEdit, QDateEdit {
    background: #ffffff;
    border: 1px solid #cfd9d3;
    border-radius: 10px;
    padding: 6px 8px;
}
QLineEdit:focus, QListWidget:focus, QTreeWidget:focus, QTableWidget:focus, QComboBox:focus, QTextEdit:focus, QDateEdit:focus {
    border: 1px solid #4e7b6b;
}
QListWidget::item, QTreeWidget::item {
    padding: 6px;
}
QListWidget::item:selected, QTreeWidget::item:selected, QTableWidget::item:selected {
    background: #d8ebe0;
    color: #183029;
}
QPushButton {
    background: #4e7b6b;
    color: #ffffff;
    border: none;
    border-radius: 10px;
    padding: 8px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background: #42695b;
}
QPushButton:disabled {
    background: #a0b6ac;
}
QPushButton[secondary="true"] {
    background: #eef4f0;
    color: #36584c;
    border: 1px solid #cfdbd4;
}
QPushButton[secondary="true"]:hover {
    background: #e4eee8;
}
QScrollArea {
    border: none;
}
QHeaderView::section {
    background: #eef4f0;
    border: none;
    border-bottom: 1px solid #d7dfdb;
    padding: 6px;
    font-weight: 600;
}
QSplitter::handle {
    background: #dce4df;
    width: 6px;
}
"""


def build_application() -> tuple[QApplication, MainWindow]:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Collective MindGraph Companion")
    app.setOrganizationName("Collective MindGraph")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)
    service = CollectiveMindGraphCompanionService()
    window = MainWindow(service)
    return app, window


def run() -> int:
    app, window = build_application()
    window.show()
    return app.exec()
