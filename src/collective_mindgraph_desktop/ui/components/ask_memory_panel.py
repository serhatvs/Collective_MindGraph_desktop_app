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
        self.ask_input.setPlaceholderText("e.g. 'What FastAPI tasks did we discuss?'")
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
        
        confidence_level = getattr(response, "confidence_level", "low") or "low"
        confidence_color = {
            "high": "#28a745",
            "medium": "#ffc107",
            "low": "#dc3545",
            "insufficient": "#6c757d"
        }.get(confidence_level, "#000")

        html = f"<b style='font-size: 12pt;'>Answer:</b><br>{getattr(response, 'short_answer', '')}<br><br>"
        html += f"<span style='color: {confidence_color};'>Confidence: {confidence_level.upper()}</span> | "
        
        raw_score = getattr(response, "evidence_coverage_score", 0.0) or 0.0
        try:
            score = float(raw_score) * 100
        except (TypeError, ValueError):
            score = 0.0
        score_color = "#28a745" if score > 80 else "#ffc107" if score > 50 else "#dc3545"
        html += f"<b>Coverage: <span style='color: {score_color};'>{score:.0f}%</span></b><br>"

        mode_used = getattr(response, "mode_used", None)
        validation_status = getattr(response, "answer_validation_status", "accepted") or "accepted"
        rejected_terms = list(getattr(response, "rejected_terms", []) or [])
        warnings = list(getattr(response, "warnings", []) or [])
        used_sources = list(getattr(response, "used_sources", []) or [])
        missing_evidence_note = getattr(response, "missing_evidence_note", None)

        if mode_used == "evidence_only_fallback":
            status_map = {
                "rejected_unsupported_terms": "added unsupported information",
                "rejected_missing_sources": "failed to cite valid sources",
                "fallback_to_evidence_only": "encountered an error"
            }
            reason = status_map.get(validation_status, "was rejected")
            warning_msg = f"LLM answer rejected because it {reason}. Showing evidence-only answer."
            if rejected_terms:
                warning_msg += f" (Rejected terms: {', '.join(rejected_terms)})"
            html += f"<br><b style='color: #dc3545;'>Warning: {warning_msg}</b>"
        elif warnings:
            html += "<br><i style='color: #856404;'>Warnings: " + ", ".join(warnings) + "</i>"
            
        if used_sources:
            html += f"<br><br><b>Used Sources:</b> {', '.join(used_sources)}"

        if missing_evidence_note:
            html += f"<br><br><b>Missing Context:</b> {missing_evidence_note}"

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
        evidence_chains = list(getattr(response, "evidence_chains", []) or [])
        source_session_ids = list(getattr(response, "source_session_ids", []) or [])
        source_segment_ids = list(getattr(response, "source_segment_ids", []) or [])

        for i, chain in enumerate(evidence_chains):
            frame = QFrame()
            frame.setFrameShape(QFrame.StyledPanel)
            frame.setStyleSheet("background: #f8f9fa; border-radius: 4px; padding: 5px;")
            flayout = QVBoxLayout(frame)
            
            chain_text = " -> ".join([f"<b>{step.node_type.upper()}</b>: {step.text}" for step in chain.steps])
            lbl = QLabel(chain_text)
            lbl.setWordWrap(True)
            flayout.addWidget(lbl)

            source = self._source_for_chain(chain)
            preview = source.get("text_preview")
            time_range = self._format_time_range(source.get("start_time"), source.get("end_time"))

            if preview:
                preview_lbl = QLabel(f"Preview: {preview}")
                preview_lbl.setWordWrap(True)
                flayout.addWidget(preview_lbl)

            if time_range:
                flayout.addWidget(QLabel(f"Time: {time_range}"))

            session_id = source.get("source_session_id") or (source_session_ids[0] if source_session_ids else "")
            segment_id = source.get("source_segment_id") or (source_segment_ids[0] if source_segment_ids else "")

            if session_id:
                btn = QPushButton("Open Source")
                btn.setFixedWidth(100)
                btn.clicked.connect(lambda _checked=False, s=session_id, seg=segment_id: self.source_navigation_requested.emit(s, seg))
                flayout.addWidget(btn)
                
            self.evidence_layout.insertWidget(self.evidence_layout.count() - 1, frame)

    @staticmethod
    def _source_for_chain(chain) -> dict[str, object]:
        for step in list(getattr(chain, "steps", []) or []):
            session_id = getattr(step, "source_session_id", None)
            segment_id = getattr(step, "source_segment_id", None)
            preview = getattr(step, "text_preview", None)
            start_time = getattr(step, "start_time", None)
            end_time = getattr(step, "end_time", None)
            source_ref_id = getattr(step, "source_reference_id", None)
            if session_id or segment_id or preview or start_time is not None or end_time is not None or source_ref_id:
                return {
                    "source_reference_id": source_ref_id,
                    "source_session_id": session_id,
                    "source_segment_id": segment_id,
                    "text_preview": preview,
                    "start_time": start_time,
                    "end_time": end_time,
                    "node_id": getattr(step, "node_id", None),
                    "node_type": getattr(step, "node_type", None),
                    "edge_path": list(getattr(step, "edge_path", []) or []),
                }
        return {}

    @staticmethod
    def _format_time_range(start_time, end_time) -> str:
        if start_time is None and end_time is None:
            return ""
        try:
            start = f"{float(start_time):.2f}s" if start_time is not None else "?"
            end = f"{float(end_time):.2f}s" if end_time is not None else "?"
        except (TypeError, ValueError):
            return ""
        return f"{start} - {end}"
