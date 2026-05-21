"""Ask Memory UI component for natural language knowledge retrieval."""

from __future__ import annotations

import logging
from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QTextEdit,
    QScrollArea,
    QFrame,
)

from ...transcription import (
    MemoryAskResponse,
    RealtimeBackendTranscriptionConfig,
    RealtimeBackendTranscriptionService,
)
from ..widgets import CardWidget

LOGGER = logging.getLogger(__name__)

class MemoryAskWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        query: str,
        mode: str,
        config: RealtimeBackendTranscriptionConfig,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._query = query
        self._mode = mode
        self._config = config

    @Slot()
    def run(self) -> None:
        try:
            service = RealtimeBackendTranscriptionService(config=self._config)
            result = service.ask_memory(self._query, mode=self._mode)
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))

class AskMemoryPanel(QWidget):
    source_navigation_requested = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config: RealtimeBackendTranscriptionConfig | None = None
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.card = CardWidget("Ask Your Memory")
        layout.addWidget(self.card)

        # Input Area
        input_container = QWidget()
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        
        self.ask_input = QLineEdit()
        self.ask_input.setPlaceholderText("e.g. 'FastAPI ile ilgili görevler neler?'")
        self.ask_input.setMinimumHeight(44)
        self.ask_input.setStyleSheet("font-size: 11pt; padding-left: 12px;")
        self.ask_input.returnPressed.connect(self._handle_ask)
        
        self.mode_selector = QComboBox()
        self.mode_selector.addItems(["Evidence Only", "LLM Assisted"])
        self.mode_selector.setMinimumHeight(44)
        
        self.ask_button = QPushButton("Ask")
        self.ask_button.setMinimumHeight(44)
        self.ask_button.clicked.connect(self._handle_ask)
        
        input_layout.addWidget(self.ask_input, 1)
        input_layout.addWidget(self.mode_selector)
        input_layout.addWidget(self.ask_button)
        self.card.body_layout.addWidget(input_container)

        # Answer Area
        self.answer_box = QTextEdit()
        self.answer_box.setReadOnly(True)
        self.answer_box.setPlaceholderText("Answers will appear here with evidence links...")
        self.answer_box.setMinimumHeight(150)
        self.card.body_layout.addWidget(self.answer_box)

        # Evidence List
        self.evidence_label = QLabel("Supporting Evidence:")
        self.evidence_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        self.card.body_layout.addWidget(self.evidence_label)
        
        self.evidence_area = QScrollArea()
        self.evidence_area.setWidgetResizable(True)
        self.evidence_container = QWidget()
        self.evidence_layout = QVBoxLayout(self.evidence_container)
        self.evidence_layout.addStretch()
        self.evidence_area.setWidget(self.evidence_container)
        self.card.body_layout.addWidget(self.evidence_area, 1)

    def set_config(self, config: RealtimeBackendTranscriptionConfig) -> None:
        self._config = config

    def _handle_ask(self) -> None:
        query = self.ask_input.text().strip()
        mode_text = self.mode_selector.currentText()
        mode = "llm_assisted" if mode_text == "LLM Assisted" else "evidence_only"
        
        if not query or not self._config:
            return

        self.ask_button.setEnabled(False)
        self.answer_box.setText("Thinking...")
        self._clear_evidence()

        self._thread = QThread()
        self._worker = MemoryAskWorker(query, mode, self._config)
        self._worker.moveToThread(self._thread)
        
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._handle_finished)
        self._worker.failed.connect(self._handle_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        
        self._thread.start()

    def _handle_finished(self, response: MemoryAskResponse) -> None:
        self.ask_button.setEnabled(True)
        
        confidence_color = {
            "high": "#28a745",
            "medium": "#ffc107",
            "low": "#dc3545",
            "insufficient": "#6c757d"
        }.get(response.confidence_level, "#000")

        html = f"<b style='font-size: 12pt;'>Answer:</b><br>{response.short_answer}<br><br>"
        html += f"<span style='color: {confidence_color};'>Confidence: {response.confidence_level.upper()}</span> | "
        
        score = response.evidence_coverage_score * 100
        score_color = "#28a745" if score > 80 else "#ffc107" if score > 50 else "#dc3545"
        html += f"<b>Coverage: <span style='color: {score_color};'>{score:.0f}%</span></b><br>"

        if response.mode_used == "evidence_only_fallback":
            status_map = {
                "rejected_unsupported_terms": "added unsupported information",
                "rejected_missing_sources": "failed to cite valid sources",
                "fallback_to_evidence_only": "encountered an error"
            }
            reason = status_map.get(response.answer_validation_status, "was rejected")
            warning_msg = f"LLM answer rejected because it {reason}. Showing evidence-only answer."
            if response.rejected_terms:
                warning_msg += f" (Rejected terms: {', '.join(response.rejected_terms)})"
            html += f"<br><b style='color: #dc3545;'>⚠️ {warning_msg}</b>"
        elif response.warnings:
            html += "<br><i style='color: #856404;'>Warnings: " + ", ".join(response.warnings) + "</i>"
            
        if response.used_sources:
            html += f"<br><br><b>Used Sources:</b> {', '.join(response.used_sources)}"

        if response.missing_evidence_note:
            html += f"<br><br><b>Missing Context:</b> {response.missing_evidence_note}"

        self.answer_box.setHtml(html)
        self._display_evidence(response)

    def _handle_failed(self, error: str) -> None:
        self.ask_button.setEnabled(True)
        self.answer_box.setText(f"Error: {error}")

    def _clear_evidence(self) -> None:
        while self.evidence_layout.count() > 1:
            item = self.evidence_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _display_evidence(self, response: MemoryAskResponse) -> None:
        for i, chain in enumerate(response.evidence_chains):
            frame = QFrame()
            frame.setFrameShape(QFrame.StyledPanel)
            frame.setStyleSheet("background: #f8f9fa; border-radius: 4px; padding: 5px;")
            flayout = QVBoxLayout(frame)
            
            chain_text = " ➔ ".join([f"<b>{step.node_type.upper()}</b>: {step.text}" for step in chain.steps])
            lbl = QLabel(chain_text)
            lbl.setWordWrap(True)
            flayout.addWidget(lbl)
            
            # Simple link to first session/segment found in response for this evidence
            # (In a real implementation we'd map each chain to its specific source)
            if response.source_session_ids:
                btn = QPushButton("Open Source")
                btn.setFixedWidth(100)
                session_id = response.source_session_ids[0]
                segment_id = response.source_segment_ids[0] if response.source_segment_ids else ""
                btn.clicked.connect(lambda s=session_id, seg=segment_id: self.source_navigation_requested.emit(s, seg))
                flayout.addWidget(btn)
                
            self.evidence_layout.insertWidget(self.evidence_layout.count() - 1, frame)
