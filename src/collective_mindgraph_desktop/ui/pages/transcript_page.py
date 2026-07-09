"""Transcript page showing side-by-side comparison of raw and corrected text."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...models import SessionDetail, TranscriptAnalysis
from ..widgets import CardWidget, EmptyStateWidget


class TranscriptPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        self.card = CardWidget("Transcript Audit")
        layout.addWidget(self.card, 1)
        self.quality_label = QLabel("")
        self.quality_label.setWordWrap(True)
        self.quality_label.setStyleSheet(
            "QLabel { color: #374151; background: #f8fafc; border: 1px solid #e5e7eb; "
            "border-radius: 6px; padding: 8px 10px; }"
        )
        self.card.body_layout.addWidget(self.quality_label)
        self.quality_label.hide()
        
        # Comparison Table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Timestamp", "Speaker", "Corrected Transcript", "Raw ASR Output"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        self.table.setStyleSheet("""
            QTableWidget::item { padding: 10px; border-bottom: 1px solid #eef2f7; }
            QTableWidget::item:selected { background: #e0eaff; color: #102036; }
        """)
        
        self.card.body_layout.addWidget(self.table)

        self.empty_state = EmptyStateWidget(
            "No transcript selected",
            "Transcribe a local audio file or select a session with transcript analysis.",
        )
        self.card.body_layout.addWidget(self.empty_state)
        self.table.hide()

    def set_detail(self, detail: SessionDetail | None) -> None:
        self.table.setRowCount(0)
        self.quality_label.hide()
        if not detail or not detail.transcripts:
            self.empty_state.set_text(
                "No transcript selected",
                "Transcribe a local audio file or select a session with transcript analysis.",
            )
            self.empty_state.show()
            self.table.hide()
            return

        # Use the latest analysis
        last_id = detail.transcripts[-1].id
        analysis = detail.transcript_analyses.get(last_id)
        if not analysis:
            self.empty_state.set_text(
                "Transcript has no analysis",
                "The session has transcript text, but raw/cleaned segment details are not available yet.",
            )
            self.empty_state.show()
            self.table.hide()
            return

        if not analysis.segments:
            self.empty_state.set_text(
                "Transcript has no segments",
                "The backend returned transcript text without segment-level raw/cleaned details.",
            )
            self.empty_state.show()
            self.table.hide()
            return

        self.empty_state.hide()
        self._show_quality_summary(analysis)
        self.table.show()

        for row, segment in enumerate(analysis.segments):
            self.table.insertRow(row)
            
            ts = f"{segment.start:.2f}s - {segment.end:.2f}s"
            
            # 1. Timestamp
            ts_item = QTableWidgetItem(ts)
            ts_item.setData(Qt.ItemDataRole.UserRole, segment.segment_id)
            ts_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            
            # 2. Speaker
            speaker = segment.speaker if segment.speaker and "Speaker_" not in segment.speaker and "UNRESOLVED_" not in segment.speaker else "Unknown"
            speaker_item = QTableWidgetItem(speaker)
            speaker_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            
            # 3. Corrected
            corrected_item = QTableWidgetItem(segment.corrected_text)
            corrected_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            corrected_item.setForeground(Qt.GlobalColor.darkBlue)
            
            # 4. Raw
            raw_item = QTableWidgetItem(segment.raw_text)
            raw_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            raw_item.setForeground(Qt.GlobalColor.gray)
            
            self.table.setItem(row, 0, ts_item)
            self.table.setItem(row, 1, speaker_item)
            self.table.setItem(row, 2, corrected_item)
            self.table.setItem(row, 3, raw_item)

    def _show_quality_summary(self, analysis: TranscriptAnalysis) -> None:
        metadata = analysis.metadata or {}
        confidence = metadata.get("transcription_confidence_estimate")
        audio_label = metadata.get("audio_quality_label")
        audio_score = metadata.get("audio_quality_score")
        warnings = metadata.get("warnings")
        confidence_text = f"Transcription Confidence: {confidence}/100" if confidence is not None else None
        audio_text = None
        if audio_label:
            audio_text = f"Audio Quality: {audio_label}"
            if audio_score is not None:
                audio_text = f"{audio_text} ({audio_score}/100)"
        warning_items = [str(item) for item in warnings] if isinstance(warnings, list) else []
        warning_text = f"Warnings: {', '.join(warning_items[:4])}" if warning_items else None
        parts = [part for part in (confidence_text, audio_text, warning_text) if part]
        if not parts:
            self.quality_label.hide()
            return
        self.quality_label.setText("  |  ".join(parts))
        self.quality_label.show()

    def scroll_to_segment(self, segment_id: str) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == segment_id:
                self.table.selectRow(row)
                self.table.scrollToItem(item)
                return
