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
from ..widgets import CardWidget


class TranscriptPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        self.card = CardWidget("Transcript Audit")
        layout.addWidget(self.card, 1)
        
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

    def set_detail(self, detail: SessionDetail | None) -> None:
        self.table.setRowCount(0)
        if not detail or not detail.transcripts:
            return

        # Use the latest analysis
        last_id = detail.transcripts[-1].id
        analysis = detail.transcript_analyses.get(last_id)
        if not analysis:
            return

        for row, segment in enumerate(analysis.segments):
            self.table.insertRow(row)
            
            ts = f"{segment.start:.2f}s - {segment.end:.2f}s"
            
            # 1. Timestamp
            ts_item = QTableWidgetItem(ts)
            ts_item.setData(Qt.ItemDataRole.UserRole, segment.segment_id)
            ts_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            
            # 2. Speaker
            speaker_item = QTableWidgetItem(segment.speaker)
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

    def scroll_to_segment(self, segment_id: str) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == segment_id:
                self.table.selectRow(row)
                self.table.scrollToItem(item)
                return
