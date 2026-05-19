"""Result card component for search results."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
    QFrame,
)


class ResultCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ResultCard")
        self.setStyleSheet("""
            QFrame#ResultCard {
                background: #ffffff;
                border: 1px solid #d6dfe8;
                border-radius: 8px;
            }
            QFrame#ResultCard:hover {
                border: 1px solid #264a7f;
                background: #f8fbff;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Header: [TYPE] Title
        self.header_layout = QHBoxLayout()
        self.type_badge = QLabel("[TYPE]")
        self.type_badge.setStyleSheet("""
            background: #eef2f7;
            color: #475867;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 9pt;
        """)
        
        self.title_label = QLabel("Result Title")
        self.title_label.setStyleSheet("font-size: 11pt; font-weight: 600; color: #102036;")
        self.title_label.setWordWrap(True)
        
        self.header_layout.addWidget(self.type_badge)
        self.header_layout.addWidget(self.title_label, 1)
        layout.addLayout(self.header_layout)

        # Body: Preview text
        self.preview_label = QLabel("Match preview context goes here...")
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet("color: #334e68; font-size: 10pt; line-height: 1.4;")
        layout.addWidget(self.preview_label)

        # Footer: Session + Meta
        self.footer_layout = QHBoxLayout()
        self.meta_label = QLabel("Session: ID | Score: 0.00")
        self.meta_label.setStyleSheet("color: #66788a; font-size: 9pt;")
        self.footer_layout.addWidget(self.meta_label, 1)
        
        self.terms_label = QLabel("Matches: ...")
        self.terms_label.setStyleSheet("color: #264a7f; font-size: 9pt; font-style: italic;")
        self.footer_layout.addWidget(self.terms_label)
        
        layout.addLayout(self.footer_layout)

    def set_result(self, res_type: str, title: str, preview: str, meta: str, terms: list[str]) -> None:
        self.type_badge.setText(res_type.upper())
        self.title_label.setText(title)
        self.preview_label.setText(preview or "")
        self.meta_label.setText(meta)
        if terms:
            self.terms_label.setText(f"Matches: {', '.join(terms)}")
            self.terms_label.show()
        else:
            self.terms_label.hide()
        
        # Color coding badges
        colors = {
            "task": "#dcfce7",
            "decision": "#fef9c3",
            "topic": "#e0e7ff",
            "transcript": "#f1f5f9"
        }
        text_colors = {
            "task": "#166534",
            "decision": "#854d0e",
            "topic": "#3730a3",
            "transcript": "#475569"
        }
        self.type_badge.setStyleSheet(f"""
            background: {colors.get(res_type.lower(), '#eef2f7')};
            color: {text_colors.get(res_type.lower(), '#475867')};
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 9pt;
        """)
