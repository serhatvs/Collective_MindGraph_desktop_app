"""Compatibility session detail panel for legacy product-loop tests."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models import (
    GraphNode,
    SessionDetail,
    Transcript,
    TranscriptAnalysis,
    TranscriptAnalysisSegment,
)


USER_ROLE = int(Qt.ItemDataRole.UserRole)


class SessionDetailPanel(QWidget):
    """Legacy aggregate panel kept for tests and older callers.

    The main application now renders session detail through individual pages,
    but several product-loop tests still exercise this combined widget API.
    """

    analysis_corrections_requested = Signal(int, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._detail: SessionDetail | None = None
        self._active_transcript_id: int | None = None

        layout = QVBoxLayout(self)

        self.transcript_list = QListWidget()
        layout.addWidget(self.transcript_list)

        self.graph_tree = QTreeWidget()
        self.graph_tree.setColumnCount(3)
        self.graph_tree.setHeaderLabels(["Node", "Branch", "Transcript"])
        layout.addWidget(self.graph_tree)

        self._analysis_labels = {"quality": QLabel("No quality report available.")}
        layout.addWidget(self._analysis_labels["quality"])

        self.segment_table = QTableWidget(0, 5)
        self.segment_table.setHorizontalHeaderLabels(["Segment", "Start", "Speaker", "Corrected", "Raw"])
        layout.addWidget(self.segment_table)

        tools = QHBoxLayout()
        self.speaker_bulk_edit = QLineEdit()
        self.rename_speaker_button = QPushButton("Rename Speaker")
        self.apply_speaker_to_selection_button = QPushButton("Apply Speaker")
        self.move_segment_up_button = QPushButton("Move Up")
        self.merge_next_button = QPushButton("Merge Next")
        self.save_corrections_button = QPushButton("Save")
        for widget in (
            self.speaker_bulk_edit,
            self.rename_speaker_button,
            self.apply_speaker_to_selection_button,
            self.move_segment_up_button,
            self.merge_next_button,
            self.save_corrections_button,
        ):
            tools.addWidget(widget)
        layout.addLayout(tools)

        self.snapshot_table = QTableWidget(0, 4)
        self.snapshot_table.setHorizontalHeaderLabels(["Created", "Nodes", "Short Hash", "Hash"])
        layout.addWidget(self.snapshot_table)

        self.speaker_stats_list = QListWidget()
        layout.addWidget(self.speaker_stats_list)

        self.insight_list = QListWidget()
        layout.addWidget(self.insight_list)

        self.rename_speaker_button.clicked.connect(self._rename_current_speaker)
        self.apply_speaker_to_selection_button.clicked.connect(self._apply_speaker_to_selection)
        self.move_segment_up_button.clicked.connect(self._move_segment_up)
        self.merge_next_button.clicked.connect(self._merge_with_next)
        self.save_corrections_button.clicked.connect(self._emit_corrections)

    def set_detail(self, detail: SessionDetail | None) -> None:
        self._detail = detail
        self._active_transcript_id = detail.transcripts[-1].id if detail and detail.transcripts else None
        self._populate_transcripts()
        self._populate_graph()
        self._populate_analysis()
        self._populate_snapshots()

    def _populate_transcripts(self) -> None:
        self.transcript_list.clear()
        if not self._detail or not self._detail.transcripts:
            item = QListWidgetItem("No transcripts recorded for this session yet.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.transcript_list.addItem(item)
            return

        for transcript in self._detail.transcripts:
            item = QListWidgetItem(
                f"{transcript.created_at}  |  Confidence {transcript.confidence:.2f}"
            )
            item.setToolTip(transcript.text)
            item.setData(Qt.ItemDataRole.UserRole, transcript.id)
            self.transcript_list.addItem(item)
        self.transcript_list.setCurrentRow(self.transcript_list.count() - 1)

    def _populate_graph(self) -> None:
        self.graph_tree.clear()
        if not self._detail:
            return
        if not self._detail.graph_nodes:
            self.graph_tree.addTopLevelItem(QTreeWidgetItem(["No graph nodes yet.", "", ""]))
            return

        nodes_by_id = {node.id: node for node in self._detail.graph_nodes}
        children: dict[int, list[GraphNode]] = {}
        roots: list[GraphNode] = []
        orphans: list[GraphNode] = []

        for node in self._detail.graph_nodes:
            if node.parent_node_id is None and node.branch_type == "root":
                roots.append(node)
            elif node.parent_node_id in nodes_by_id:
                children.setdefault(node.parent_node_id or 0, []).append(node)
            else:
                orphans.append(node)

        transcript_by_id = {item.id: item for item in self._detail.transcripts}
        for root in sorted(roots, key=lambda item: item.id):
            self.graph_tree.addTopLevelItem(
                self._build_graph_item(root, transcript_by_id, children)
            )

        if orphans:
            bucket = QTreeWidgetItem(["Unlinked", "", ""])
            bucket.setToolTip(0, "Nodes with missing or invalid parent references.")
            for orphan in sorted(orphans, key=self._node_sort_key):
                bucket.addChild(self._build_graph_item(orphan, transcript_by_id, children))
            self.graph_tree.addTopLevelItem(bucket)

        self.graph_tree.expandAll()

    def _build_graph_item(
        self,
        node: GraphNode,
        transcript_by_id: dict[int, Transcript],
        children: dict[int, list[GraphNode]],
    ) -> QTreeWidgetItem:
        branch = self._branch_label(node)
        transcript_text = self._transcript_text(node, transcript_by_id)
        item = QTreeWidgetItem([node.node_text, branch, self._truncate(transcript_text)])
        item.setToolTip(1, f"{branch}\n{node.override_reason}" if node.override_reason else branch)
        item.setToolTip(2, transcript_text)
        for child in sorted(children.get(node.id, []), key=self._node_sort_key):
            item.addChild(self._build_graph_item(child, transcript_by_id, children))
        return item

    @staticmethod
    def _node_sort_key(node: GraphNode) -> tuple[int, int, int]:
        branch_order = 0 if node.branch_type == "main" else 1 if node.branch_type == "side" else 2
        return branch_order, node.branch_slot or 0, node.id

    @staticmethod
    def _branch_label(node: GraphNode) -> str:
        if node.branch_type == "side" and node.branch_slot is not None:
            return f"side-{node.branch_slot}"
        return node.branch_type

    @staticmethod
    def _transcript_text(node: GraphNode, transcript_by_id: dict[int, Transcript]) -> str:
        if node.transcript_id is None or node.transcript_id not in transcript_by_id:
            return "No transcript linked"
        return transcript_by_id[node.transcript_id].text

    @staticmethod
    def _truncate(text: str, limit: int = 72) -> str:
        if len(text) <= limit:
            return text
        return f"{text[: limit - 3]}..."

    def _populate_analysis(self) -> None:
        analysis = self._active_analysis()
        self._populate_quality(analysis)
        self._populate_segments(analysis)
        self._populate_speaker_stats(analysis)
        self._populate_insights(analysis)

    def _active_analysis(self) -> TranscriptAnalysis | None:
        if not self._detail or self._active_transcript_id is None:
            return None
        return self._detail.transcript_analyses.get(self._active_transcript_id)

    def _populate_quality(self, analysis: TranscriptAnalysis | None) -> None:
        report = analysis.quality_report if analysis else None
        if report is None:
            self._analysis_labels["quality"].setText("No quality report available.")
            return
        text = (
            f"{report.speaker_count} speakers  |  overlap {report.overlap_ratio:.2f}  |  "
            f"coverage {report.word_timing_coverage:.2f}"
        )
        if report.warnings:
            text += "  |  " + " | ".join(report.warnings)
        self._analysis_labels["quality"].setText(text)

    def _populate_segments(self, analysis: TranscriptAnalysis | None) -> None:
        self.segment_table.setRowCount(0)
        if analysis is None:
            return
        for segment in analysis.segments:
            self._append_segment_row(segment)

    def _append_segment_row(self, segment: TranscriptAnalysisSegment) -> None:
        row = self.segment_table.rowCount()
        self.segment_table.insertRow(row)
        values = [
            segment.segment_id,
            self._format_time(segment.start),
            segment.speaker,
            segment.corrected_text,
            segment.raw_text,
        ]
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            if column == 0:
                item.setData(Qt.ItemDataRole.UserRole, segment.segment_id)
                item.setData(Qt.ItemDataRole.UserRole + 1, segment)
            self.segment_table.setItem(row, column, item)

    @staticmethod
    def _format_time(seconds: float) -> str:
        minutes = int(seconds // 60)
        remaining = seconds - (minutes * 60)
        return f"{minutes:02d}:{remaining:06.3f}"

    def _populate_speaker_stats(self, analysis: TranscriptAnalysis | None) -> None:
        self.speaker_stats_list.clear()
        if not analysis or not analysis.speaker_stats:
            item = QListWidgetItem("No speaker stats available.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.speaker_stats_list.addItem(item)
            return
        for stat in analysis.speaker_stats:
            item = QListWidgetItem(
                f"{stat.speaker}  |  {stat.segment_count} segments  |  "
                f"{stat.speaking_seconds:.1f}s spoken"
            )
            item.setToolTip(
                f"{stat.speaker}\nSegments: {stat.segment_count}\n"
                f"Speaking seconds: {stat.speaking_seconds:.3f}\n"
                f"Overlap segments: {stat.overlap_segments}"
            )
            self.speaker_stats_list.addItem(item)

    def _populate_insights(self, analysis: TranscriptAnalysis | None) -> None:
        self.insight_list.clear()
        if not analysis or not (analysis.topics or analysis.decisions or analysis.action_items):
            item = QListWidgetItem("No topics, decisions, or action items available.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.insight_list.addItem(item)
            return
        for topic in analysis.topics:
            self.insight_list.addItem(
                f"Topic: {topic.label} ({self._format_time(topic.start)} - {self._format_time(topic.end)})"
            )
        for decision in analysis.decisions:
            self.insight_list.addItem(f"Decision: {decision.decision}")
        for action in analysis.action_items:
            self.insight_list.addItem(f"Action: {action.title}")

    def _populate_snapshots(self) -> None:
        self.snapshot_table.setRowCount(0)
        if not self._detail or not self._detail.snapshots:
            self.snapshot_table.insertRow(0)
            self.snapshot_table.setItem(0, 0, QTableWidgetItem("No snapshots available."))
            self.snapshot_table.setItem(0, 1, QTableWidgetItem(""))
            self.snapshot_table.setItem(0, 2, QTableWidgetItem(""))
            self.snapshot_table.setItem(0, 3, QTableWidgetItem(""))
            return
        for snapshot in self._detail.snapshots:
            row = self.snapshot_table.rowCount()
            self.snapshot_table.insertRow(row)
            short_hash = f"{snapshot.hash_sha256[:12]}..."
            values = [snapshot.created_at, str(snapshot.node_count), short_hash, snapshot.hash_sha256]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in (2, 3):
                    item.setToolTip(snapshot.hash_sha256)
                self.snapshot_table.setItem(row, column, item)

    def _rename_current_speaker(self) -> None:
        new_speaker = self.speaker_bulk_edit.text().strip()
        current = self.segment_table.currentRow()
        if not new_speaker or current < 0:
            return
        current_speaker = self.segment_table.item(current, 2).text()
        for row in range(self.segment_table.rowCount()):
            if self.segment_table.item(row, 2).text() == current_speaker:
                self.segment_table.item(row, 2).setText(new_speaker)

    def _apply_speaker_to_selection(self) -> None:
        new_speaker = self.speaker_bulk_edit.text().strip()
        if not new_speaker:
            return
        selected_rows = {index.row() for index in self.segment_table.selectionModel().selectedRows()}
        for row in sorted(selected_rows):
            self.segment_table.item(row, 2).setText(new_speaker)

    def _move_segment_up(self) -> None:
        row = self.segment_table.currentRow()
        if row <= 0:
            return
        self._swap_rows(row, row - 1)
        self.segment_table.selectRow(row - 1)

    def _swap_rows(self, first: int, second: int) -> None:
        first_values = [self.segment_table.takeItem(first, column) for column in range(self.segment_table.columnCount())]
        second_values = [self.segment_table.takeItem(second, column) for column in range(self.segment_table.columnCount())]
        for column, item in enumerate(first_values):
            self.segment_table.setItem(second, column, item)
        for column, item in enumerate(second_values):
            self.segment_table.setItem(first, column, item)

    def _merge_with_next(self) -> None:
        row = self.segment_table.currentRow()
        if row < 0 or row >= self.segment_table.rowCount() - 1:
            return
        corrected = " ".join(
            item.text().strip()
            for item in (self.segment_table.item(row, 3), self.segment_table.item(row + 1, 3))
            if item and item.text().strip()
        )
        raw = " ".join(
            item.text().strip()
            for item in (self.segment_table.item(row, 4), self.segment_table.item(row + 1, 4))
            if item and item.text().strip()
        )
        self.segment_table.item(row, 3).setText(corrected)
        self.segment_table.item(row, 4).setText(raw)
        base = self.segment_table.item(row, 0).data(Qt.ItemDataRole.UserRole + 1)
        next_segment = self.segment_table.item(row + 1, 0).data(Qt.ItemDataRole.UserRole + 1)
        if isinstance(base, TranscriptAnalysisSegment) and isinstance(next_segment, TranscriptAnalysisSegment):
            merged_start = round((base.start + next_segment.start) / 2.0, 3)
            self.segment_table.item(row, 1).setText(self._format_time(merged_start))
            self.segment_table.item(row, 0).setData(
                Qt.ItemDataRole.UserRole + 1,
                replace(
                    base,
                    start=merged_start,
                    end=max(base.end, next_segment.end),
                    corrected_text=corrected,
                    raw_text=raw,
                ),
            )
        self.segment_table.removeRow(row + 1)

    def _emit_corrections(self) -> None:
        if self._active_transcript_id is None:
            return
        segments: list[TranscriptAnalysisSegment] = []
        for row in range(self.segment_table.rowCount()):
            base = self.segment_table.item(row, 0).data(Qt.ItemDataRole.UserRole + 1)
            if not isinstance(base, TranscriptAnalysisSegment):
                continue
            segments.append(
                replace(
                    base,
                    speaker=self.segment_table.item(row, 2).text(),
                    corrected_text=self.segment_table.item(row, 3).text(),
                    raw_text=self.segment_table.item(row, 4).text(),
                )
            )
        self.analysis_corrections_requested.emit(self._active_transcript_id, segments)
