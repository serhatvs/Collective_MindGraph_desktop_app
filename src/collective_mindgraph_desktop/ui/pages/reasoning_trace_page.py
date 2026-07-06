"""Reasoning Trace page showing evidence chains from the knowledge graph."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..widgets import CardWidget


class ReasoningTracePage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        header = QLabel("Graph Evidence Reasoning")
        header.setStyleSheet("font-size: 14pt; font-weight: bold; color: #264a7f;")
        layout.addWidget(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        layout.addWidget(self.scroll)

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(16)
        self.scroll.setWidget(self.container)

        self.empty_label = QLabel("Run a graph query to see reasoning evidence.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.container_layout.addWidget(self.empty_label)

    def set_reasoning_result(self, query: str, chains: list[dict], warnings: list[str]) -> None:
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if warnings:
            warn_card = CardWidget("Warnings")
            warn_card.body_layout.addWidget(QLabel("\n".join(warnings)))
            self.container_layout.addWidget(warn_card)

        if not chains:
            self.container_layout.addWidget(QLabel("No evidence chains found for this query."))
            return

        for idx, chain in enumerate(chains):
            card = CardWidget(f"Evidence Chain #{idx + 1}")
            steps_layout = QVBoxLayout()

            steps = chain.get("steps", [])
            for i, step in enumerate(steps):
                step_text = f"<b>{step['node_type']}</b>: {step['text']}"
                if step.get("edge_type"):
                    direction = "OUT" if step.get("direction") == "out" else "IN"
                    step_text = f"<i>{direction} ({step['edge_type']})</i><br>{step_text}"

                label = QLabel(step_text)
                label.setTextFormat(Qt.TextFormat.RichText)
                label.setWordWrap(True)
                label.setStyleSheet(
                    "padding: 8px; background: #f8fafc; border-radius: 4px; border: 1px solid #e2e8f0;"
                )
                steps_layout.addWidget(label)

                if i < len(steps) - 1:
                    arrow = QLabel("then")
                    arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    steps_layout.addWidget(arrow)

            card.body_layout.addLayout(steps_layout)
            self.container_layout.addWidget(card)

        self.container_layout.addStretch(1)
