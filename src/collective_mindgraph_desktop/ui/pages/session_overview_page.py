"""Session overview page showing metadata and high-level summary."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
    QScrollArea,
)

from ...models import SessionDetail, TranscriptAnalysis
from ..widgets import CardWidget, MetricPill


class SessionOverviewPage(QWidget):
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
        
        # 1. Metadata Card
        self.meta_card = CardWidget("Session Metadata")
        self.container_layout.addWidget(self.meta_card)
        
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(12)
        
        self.labels = {
            "title": QLabel("-"),
            "id": QLabel("-"),
            "created": QLabel("-"),
            "language": QLabel("-"),
            "provider": QLabel("-"),
        }
        for label in self.labels.values():
            label.setStyleSheet("font-weight: 600; color: #102036;")
            
        form.addRow("Session Title", self.labels["title"])
        form.addRow("Session ID", self.labels["id"])
        form.addRow("Created At", self.labels["created"])
        form.addRow("Language", self.labels["language"])
        form.addRow("ASR Provider", self.labels["provider"])
        self.meta_card.body_layout.addLayout(form)
        
        # 2. Stats Row
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)
        self.pills = {
            "segments": MetricPill("Segments"),
            "tasks": MetricPill("Tasks"),
            "decisions": MetricPill("Decisions"),
            "topics": MetricPill("Topics"),
        }
        for pill in self.pills.values():
            stats_layout.addWidget(pill)
        self.container_layout.addLayout(stats_layout)
        
        # 3. Summary Card
        self.summary_card = CardWidget("Intelligence Summary")
        self.container_layout.addWidget(self.summary_card)
        
        self.summary_text = QLabel("Select a session to view the summary.")
        self.summary_text.setWordWrap(True)
        self.summary_text.setStyleSheet("font-size: 11pt; line-height: 1.5; color: #334e68;")
        self.summary_card.body_layout.addWidget(self.summary_text)
        
        self.container_layout.addStretch(1)

    def set_detail(self, detail: SessionDetail | None) -> None:
        if not detail:
            self.labels["title"].setText("-")
            self.labels["id"].setText("-")
            self.labels["created"].setText("-")
            self.labels["language"].setText("-")
            self.labels["provider"].setText("-")
            self.summary_text.setText("Select a session.")
            for pill in self.pills.values():
                pill.set_value(0)
            return

        session = detail.session
        self.labels["title"].setText(session.title)
        self.labels["id"].setText(str(session.id))
        self.labels["created"].setText(session.created_at)
        
        # Get analysis if available
        analysis: TranscriptAnalysis | None = None
        if detail.transcripts:
            last_id = detail.transcripts[-1].id
            analysis = detail.transcript_analyses.get(last_id)
            
        if analysis:
            self.labels["language"].setText(analysis.corrected_text_output[:2] if "tr" in analysis.corrected_text_output.lower() else "tr") # heuristic or add lang to analysis
            # Actually we should use analysis models properly
            self.labels["provider"].setText(analysis.source_provider)
            self.summary_text.setText(analysis.summary or "No summary available.")
            self.pills["segments"].set_value(len(analysis.segments))
            self.pills["tasks"].set_value(len(analysis.action_items))
            self.pills["decisions"].set_value(len(analysis.decisions))
            self.pills["topics"].set_value(len(analysis.topics))
        else:
            self.labels["language"].setText("-")
            self.labels["provider"].setText("-")
            self.summary_text.setText("No analysis found for this session.")
            for pill in self.pills.values():
                pill.set_value(0)
