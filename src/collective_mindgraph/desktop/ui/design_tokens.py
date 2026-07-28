"""Shared visual tokens for every desktop workspace."""

from __future__ import annotations

COLORS = {
    "canvas": "#F5F7FA",
    "surface": "#FFFFFF",
    "surface_subtle": "#EEF2F7",
    "text": "#172033",
    "muted": "#687386",
    "primary": "#3157D5",
    "primary_hover": "#2448BC",
    "border": "#D8DFE9",
    "success": "#16835D",
    "warning": "#B26A00",
    "danger": "#C63D4F",
}

SPACING = {"xs": 4, "sm": 8, "md": 12, "lg": 20, "xl": 28}
RADIUS = {"sm": 6, "md": 10, "lg": 16}
TYPE = {"body": 13, "label": 12, "title": 24, "hero": 30}


def application_stylesheet() -> str:
    return f"""
    QWidget {{
        color: {COLORS["text"]};
        font-family: "Segoe UI";
        font-size: {TYPE["body"]}px;
    }}
    QMainWindow, QWidget#AppCanvas {{
        background: {COLORS["canvas"]};
    }}
    QFrame#Navigation {{
        background: #17233D;
        border: none;
    }}
    QPushButton#NavButton {{
        color: #DCE5F5;
        background: transparent;
        border: none;
        border-radius: {RADIUS["md"]}px;
        padding: 11px 14px;
        text-align: left;
        font-weight: 600;
    }}
    QPushButton#NavButton:hover {{
        background: #243454;
    }}
    QPushButton#NavButton:checked {{
        color: white;
        background: {COLORS["primary"]};
    }}
    QFrame#Card {{
        background: {COLORS["surface"]};
        border: 1px solid {COLORS["border"]};
        border-radius: {RADIUS["lg"]}px;
    }}
    QLabel#WorkspaceTitle {{
        font-size: {TYPE["title"]}px;
        font-weight: 700;
    }}
    QLabel#HeroTitle {{
        font-size: {TYPE["hero"]}px;
        font-weight: 750;
    }}
    QLabel#Muted {{
        color: {COLORS["muted"]};
    }}
    QPushButton {{
        background: {COLORS["surface"]};
        border: 1px solid {COLORS["border"]};
        border-radius: {RADIUS["sm"]}px;
        min-height: 34px;
        padding: 0 14px;
    }}
    QPushButton:hover {{
        border-color: {COLORS["primary"]};
    }}
    QPushButton#Primary {{
        color: white;
        background: {COLORS["primary"]};
        border-color: {COLORS["primary"]};
        font-weight: 650;
    }}
    QPushButton#Primary:hover {{
        background: {COLORS["primary_hover"]};
    }}
    QLineEdit, QComboBox, QPlainTextEdit, QTextEdit, QTableWidget {{
        background: {COLORS["surface"]};
        border: 1px solid {COLORS["border"]};
        border-radius: {RADIUS["sm"]}px;
        padding: 7px;
        selection-background-color: {COLORS["primary"]};
    }}
    QTabWidget::pane {{
        border: 1px solid {COLORS["border"]};
        border-radius: {RADIUS["md"]}px;
        background: {COLORS["surface"]};
    }}
    QTabBar::tab {{
        padding: 9px 16px;
        color: {COLORS["muted"]};
    }}
    QTabBar::tab:selected {{
        color: {COLORS["primary"]};
        font-weight: 650;
    }}
    """
