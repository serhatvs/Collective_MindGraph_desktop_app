"""Insights page showing Tasks, Decisions, and Topics."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
    QScrollArea,
)

from ...models import SessionDetail, TranscriptAnalysis
from ..widgets import CardWidget


class InsightsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        layout.addWidget(scroll)
        
        container = QWidget()
        self.container_layout = QVBoxLayout(container)
        self.container_layout.setContentsMargins(24, 24, 24, 24)
        self.container_layout.setSpacing(24)
        scroll.setWidget(container)
        
        # 1. Tasks Card
        self.tasks_card = CardWidget("Action Items (Tasks)")
        self.tasks_list = QListWidget()
        self.tasks_list.setStyleSheet("QListWidget::item { padding: 8px; }")
        self.tasks_card.body_layout.addWidget(self.tasks_list)
        self.container_layout.addWidget(self.tasks_card)
        
        # 2. Decisions Card
        self.decisions_card = CardWidget("Decisions")
        self.decisions_list = QListWidget()
        self.decisions_list.setStyleSheet("QListWidget::item { padding: 8px; }")
        self.decisions_card.body_layout.addWidget(self.decisions_list)
        self.container_layout.addWidget(self.decisions_card)
        
        # 3. Topics Card
        self.topics_card = CardWidget("Topics")
        self.topics_list = QListWidget()
        self.topics_list.setStyleSheet("QListWidget::item { padding: 8px; }")
        self.topics_card.body_layout.addWidget(self.topics_list)
        self.container_layout.addWidget(self.topics_card)
        
        self.container_layout.addStretch(1)

    def set_detail(self, detail: SessionDetail | None) -> None:
        self.tasks_list.clear()
        self.decisions_list.clear()
        self.topics_list.clear()
        
        if not detail or not detail.transcripts:
            return

        last_id = detail.transcripts[-1].id
        analysis = detail.transcript_analyses.get(last_id)
        if not analysis:
            return

        # Tasks
        if analysis.action_items:
            for task in analysis.action_items:
                item = QListWidgetItem(f"✅ {task.title}")
                if task.responsible_person:
                    item.setText(f"{item.text()} (Resp: {task.responsible_person})")
                item.setToolTip(f"Source: {task.source_segment_id}\nNote: {task.confidence_note}")
                self.tasks_list.addItem(item)
        else:
            self.tasks_list.addItem("No tasks identified.")

        # Decisions
        if analysis.decisions:
            for decision in analysis.decisions:
                item = QListWidgetItem(f"💡 {decision.decision}")
                item.setToolTip(f"Source: {decision.source_segment_id}\nContext: {decision.reason_context}")
                self.decisions_list.addItem(item)
        else:
            self.decisions_list.addItem("No decisions identified.")

        # Topics
        if analysis.topics:
            for topic in analysis.topics:
                item = QListWidgetItem(f"🏷️ {topic.label}")
                item.setToolTip(f"Range: {topic.start:.2f}s - {topic.end:.2f}s")
                self.topics_list.addItem(item)
        else:
            self.topics_list.addItem("No topics identified.")
