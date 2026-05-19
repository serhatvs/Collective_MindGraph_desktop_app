"""Diagnostics page showing technical backend and pipeline status."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
    QScrollArea,
)

from ...models import SessionDetail, TranscriptAnalysis
from ..widgets import CardWidget


class DiagnosticsPage(QWidget):
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
        
        # 1. Pipeline Status Card
        self.status_card = CardWidget("Technical Diagnostics")
        self.container_layout.addWidget(self.status_card)
        
        self.form = QFormLayout()
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.form.setSpacing(12)
        
        self.labels = {
            "backend_url": QLabel("http://127.0.0.1:8081"),
            "asr_provider": QLabel("-"),
            "llm_provider": QLabel("-"),
            "offline_mode": QLabel("ACTIVE (Strict Local-First)"),
            "processing_time": QLabel("-"),
            "raw_length": QLabel("-"),
            "clean_length": QLabel("-"),
        }
        for label in self.labels.values():
            label.setStyleSheet("font-family: 'Consolas', monospace; color: #264a7f;")
            
        self.form.addRow("Backend URL", self.labels["backend_url"])
        self.form.addRow("ASR Provider", self.labels["asr_provider"])
        self.form.addRow("LLM Provider", self.labels["llm_provider"])
        self.form.addRow("Security Mode", self.labels["offline_mode"])
        self.form.addRow("Analysis Duration", self.labels["processing_time"])
        self.form.addRow("Raw Transcript Char Count", self.labels["raw_length"])
        self.form.addRow("Clean Transcript Char Count", self.labels["clean_length"])
        
        self.status_card.body_layout.addLayout(self.form)
        
        # 2. Safety Card
        self.safety_card = CardWidget("Offline Safety Guards")
        self.container_layout.addWidget(self.safety_card)
        
        safety_text = QLabel(
            "✓ External cloud AI providers (Deepgram, Bedrock) are REMOVED.\n"
            "✓ Mandatory URL validation restricts API calls to local/private network ranges.\n"
            "✓ Local model verification prevents silent auto-downloads."
        )
        safety_text.setStyleSheet("color: #19693d; font-weight: 600;")
        self.safety_card.body_layout.addWidget(safety_text)
        
        self.container_layout.addStretch(1)

    def set_detail(self, detail: SessionDetail | None) -> None:
        if not detail or not detail.transcripts:
            return

        last_id = detail.transcripts[-1].id
        analysis = detail.transcript_analyses.get(last_id)
        if not analysis:
            return

        self.labels["asr_provider"].setText(analysis.source_provider)
        # Diagnostics models are in backend but we can show basic stats
        self.labels["raw_length"].setText(str(len(analysis.raw_text_output)))
        self.labels["clean_length"].setText(str(len(analysis.corrected_text_output)))
        self.labels["processing_time"].setText("Calculated on backend")
