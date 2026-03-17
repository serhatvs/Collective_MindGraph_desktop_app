"""Session detail area."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHeaderView,
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
    Snapshot,
    Transcript,
    TranscriptAnalysis,
    TranscriptAnalysisSegment,
)
from .widgets import CardWidget


class SessionDetailPanel(QWidget):
    analysis_corrections_requested = Signal(int, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._detail: SessionDetail | None = None
        self._current_analysis: TranscriptAnalysis | None = None

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        root_layout.addLayout(content_layout)

        self.overview_card = CardWidget("Session Overview")
        overview_form = QFormLayout()
        overview_form.setHorizontalSpacing(24)
        overview_form.setVerticalSpacing(8)
        self._overview_labels = {
            "title": QLabel("-"),
            "device_id": QLabel("-"),
            "status": QLabel("-"),
            "created_at": QLabel("-"),
            "updated_at": QLabel("-"),
            "transcript_count": QLabel("0"),
            "node_count": QLabel("0"),
            "snapshot_count": QLabel("0"),
        }
        self._overview_labels["title"].setWordWrap(True)
        overview_form.addRow("Title", self._overview_labels["title"])
        overview_form.addRow("Device ID", self._overview_labels["device_id"])
        overview_form.addRow("Status", self._overview_labels["status"])
        overview_form.addRow("Created", self._overview_labels["created_at"])
        overview_form.addRow("Updated", self._overview_labels["updated_at"])
        overview_form.addRow("Transcript Count", self._overview_labels["transcript_count"])
        overview_form.addRow("Graph Node Count", self._overview_labels["node_count"])
        overview_form.addRow("Snapshot Count", self._overview_labels["snapshot_count"])
        self.overview_card.body_layout.addLayout(overview_form)
        content_layout.addWidget(self.overview_card)

        self.transcript_card = CardWidget("Transcript Timeline")
        self.transcript_list = QListWidget()
        self.transcript_list.currentRowChanged.connect(self._handle_transcript_selection_changed)
        self.transcript_card.body_layout.addWidget(self.transcript_list)
        content_layout.addWidget(self.transcript_card)

        self.analysis_card = CardWidget("Conversation Analysis")
        analysis_form = QFormLayout()
        analysis_form.setHorizontalSpacing(24)
        analysis_form.setVerticalSpacing(8)
        self._analysis_labels = {
            "provider": QLabel("-"),
            "conversation_id": QLabel("-"),
            "summary": QLabel("No backend analysis attached."),
            "quality": QLabel("-"),
        }
        self._analysis_labels["summary"].setWordWrap(True)
        self._analysis_labels["quality"].setWordWrap(True)
        analysis_form.addRow("Provider", self._analysis_labels["provider"])
        analysis_form.addRow("Conversation ID", self._analysis_labels["conversation_id"])
        analysis_form.addRow("Summary", self._analysis_labels["summary"])
        analysis_form.addRow("Quality", self._analysis_labels["quality"])
        self.analysis_card.body_layout.addLayout(analysis_form)

        speaker_label = QLabel("Speaker Stats")
        speaker_label.setObjectName("MutedText")
        self.analysis_card.body_layout.addWidget(speaker_label)

        self.speaker_stats_list = QListWidget()
        self.analysis_card.body_layout.addWidget(self.speaker_stats_list)

        insight_label = QLabel("Topics / Decisions / Action Items")
        insight_label.setObjectName("MutedText")
        self.analysis_card.body_layout.addWidget(insight_label)

        self.insight_list = QListWidget()
        self.analysis_card.body_layout.addWidget(self.insight_list)

        segments_label = QLabel("Editable Transcript Segments")
        segments_label.setObjectName("MutedText")
        self.analysis_card.body_layout.addWidget(segments_label)

        self.segment_table = QTableWidget(0, 5)
        self.segment_table.setHorizontalHeaderLabels(["Start", "End", "Speaker", "Corrected Text", "Raw Text"])
        self.segment_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.segment_table.verticalHeader().setVisible(False)
        self.segment_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.segment_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.segment_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.segment_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.segment_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.analysis_card.body_layout.addWidget(self.segment_table)

        correction_tools_row = QHBoxLayout()
        correction_tools_row.setSpacing(8)

        self.speaker_bulk_edit = QLineEdit()
        self.speaker_bulk_edit.setPlaceholderText("Rename or merge speaker into...")
        correction_tools_row.addWidget(self.speaker_bulk_edit, 1)

        self.rename_speaker_button = QPushButton("Rename Speaker Everywhere")
        self.rename_speaker_button.setProperty("secondary", True)
        self.rename_speaker_button.clicked.connect(self._rename_selected_speaker_everywhere)
        correction_tools_row.addWidget(self.rename_speaker_button)

        self.apply_speaker_to_selection_button = QPushButton("Apply Speaker to Selection")
        self.apply_speaker_to_selection_button.setProperty("secondary", True)
        self.apply_speaker_to_selection_button.clicked.connect(self._apply_speaker_to_selection)
        correction_tools_row.addWidget(self.apply_speaker_to_selection_button)

        self.move_segment_up_button = QPushButton("Move Up")
        self.move_segment_up_button.setProperty("secondary", True)
        self.move_segment_up_button.clicked.connect(lambda: self._move_selected_segment(-1))
        correction_tools_row.addWidget(self.move_segment_up_button)

        self.move_segment_down_button = QPushButton("Move Down")
        self.move_segment_down_button.setProperty("secondary", True)
        self.move_segment_down_button.clicked.connect(lambda: self._move_selected_segment(1))
        correction_tools_row.addWidget(self.move_segment_down_button)

        self.merge_next_button = QPushButton("Merge With Next")
        self.merge_next_button.setProperty("secondary", True)
        self.merge_next_button.clicked.connect(self._merge_selected_with_next)
        correction_tools_row.addWidget(self.merge_next_button)

        self.analysis_card.body_layout.addLayout(correction_tools_row)

        self.save_corrections_button = QPushButton("Save Corrections")
        self.save_corrections_button.clicked.connect(self._emit_corrections)
        self.save_corrections_button.setEnabled(False)
        self.analysis_card.body_layout.addWidget(self.save_corrections_button)
        content_layout.addWidget(self.analysis_card)

        self.graph_card = CardWidget("Graph Tree")
        self.graph_tree = QTreeWidget()
        self.graph_tree.setColumnCount(4)
        self.graph_tree.setHeaderLabels(["Node", "Branch", "Transcript", "Created"])
        self.graph_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.graph_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.graph_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.graph_tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.graph_card.body_layout.addWidget(self.graph_tree)
        content_layout.addWidget(self.graph_card)

        self.snapshot_card = CardWidget("Snapshot History")
        self.snapshot_table = QTableWidget(0, 4)
        self.snapshot_table.setHorizontalHeaderLabels(["Created", "Node Count", "Short Hash", "Full Hash"])
        self.snapshot_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.snapshot_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.snapshot_table.verticalHeader().setVisible(False)
        self.snapshot_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.snapshot_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.snapshot_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.snapshot_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.snapshot_card.body_layout.addWidget(self.snapshot_table)
        content_layout.addWidget(self.snapshot_card)
        content_layout.addStretch(1)

    def set_detail(self, detail: SessionDetail | None) -> None:
        if detail is None:
            self._detail = None
            self._current_analysis = None
            return

        self._detail = detail
        self._overview_labels["title"].setText(detail.session.title)
        self._overview_labels["device_id"].setText(detail.session.device_id)
        self._overview_labels["status"].setText(detail.session.status.upper())
        self._overview_labels["created_at"].setText(detail.session.created_at)
        self._overview_labels["updated_at"].setText(detail.session.updated_at)
        self._overview_labels["transcript_count"].setText(str(len(detail.transcripts)))
        self._overview_labels["node_count"].setText(str(len(detail.graph_nodes)))
        self._overview_labels["snapshot_count"].setText(str(len(detail.snapshots)))

        self._populate_analysis(None)
        self._populate_transcripts(detail.transcripts)
        self._populate_graph(detail.graph_nodes, detail.transcripts)
        self._populate_snapshots(detail.snapshots)

    def _populate_transcripts(self, transcripts: list[Transcript]) -> None:
        self.transcript_list.clear()
        if not transcripts:
            item = QListWidgetItem("No transcripts recorded for this session yet.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.transcript_list.addItem(item)
            return

        for transcript in transcripts:
            item = QListWidgetItem(
                f"{transcript.created_at}  |  Confidence {transcript.confidence:.2f}\n{self._truncate(transcript.text, 160)}"
            )
            item.setData(Qt.ItemDataRole.UserRole, transcript.id)
            item.setToolTip(transcript.text)
            self.transcript_list.addItem(item)
        self.transcript_list.setCurrentRow(len(transcripts) - 1)

    def _handle_transcript_selection_changed(self, row_index: int) -> None:
        if self._detail is None or row_index < 0:
            self._populate_analysis(None)
            return
        item = self.transcript_list.item(row_index)
        if item is None:
            self._populate_analysis(None)
            return
        transcript_id = int(item.data(Qt.ItemDataRole.UserRole))
        self._populate_analysis(self._detail.transcript_analyses.get(transcript_id))

    def _populate_analysis(self, analysis: TranscriptAnalysis | None) -> None:
        self._current_analysis = analysis
        self.speaker_stats_list.clear()
        self.insight_list.clear()
        self.segment_table.setRowCount(0)
        self.save_corrections_button.setEnabled(analysis is not None)
        self._sync_correction_controls(analysis is not None and bool(analysis.segments))

        if analysis is None:
            self._analysis_labels["provider"].setText("-")
            self._analysis_labels["conversation_id"].setText("-")
            self._analysis_labels["summary"].setText("No backend analysis attached to the selected transcript.")
            self._analysis_labels["quality"].setText("-")
            placeholder = QListWidgetItem("No speaker stats available.")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.speaker_stats_list.addItem(placeholder)
            insight_placeholder = QListWidgetItem("No topics, decisions, or action items available.")
            insight_placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.insight_list.addItem(insight_placeholder)
            self.segment_table.setRowCount(1)
            self.segment_table.setItem(0, 0, QTableWidgetItem("No segments available."))
            for column_index in range(1, 5):
                self.segment_table.setItem(0, column_index, QTableWidgetItem(""))
            return

        self._analysis_labels["provider"].setText(analysis.source_provider)
        self._analysis_labels["conversation_id"].setText(analysis.backend_conversation_id or "-")
        self._analysis_labels["summary"].setText(analysis.summary or "No summary returned.")
        self._analysis_labels["quality"].setText(self._quality_summary(analysis))

        if analysis.speaker_stats:
            for stat in analysis.speaker_stats:
                item = QListWidgetItem(
                    f"{stat.speaker}  |  {stat.segment_count} segments  |  {stat.speaking_seconds:.1f}s spoken"
                )
                item.setToolTip(
                    f"{stat.speaker}\nSegments: {stat.segment_count}\n"
                    f"Speaking seconds: {stat.speaking_seconds:.3f}\n"
                    f"Overlap segments: {stat.overlap_segments}"
                )
                self.speaker_stats_list.addItem(item)
        else:
            placeholder = QListWidgetItem("No speaker stats available.")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.speaker_stats_list.addItem(placeholder)

        insight_entries: list[str] = []
        insight_entries.extend(
            f"Topic: {topic.label} ({self._format_seconds(topic.start)} - {self._format_seconds(topic.end)})"
            for topic in analysis.topics
        )
        insight_entries.extend(f"Decision: {item}" for item in analysis.decisions)
        insight_entries.extend(f"Action: {item}" for item in analysis.action_items)
        if insight_entries:
            for entry in insight_entries:
                self.insight_list.addItem(QListWidgetItem(entry))
        else:
            placeholder = QListWidgetItem("No topics, decisions, or action items available.")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.insight_list.addItem(placeholder)

        for row_index, segment in enumerate(analysis.segments):
            self.segment_table.insertRow(row_index)
            start_item = QTableWidgetItem(self._format_seconds(segment.start))
            start_item.setData(Qt.ItemDataRole.UserRole, segment.segment_id)
            start_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            end_item = QTableWidgetItem(self._format_seconds(segment.end))
            end_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            speaker_item = QTableWidgetItem(segment.speaker)
            corrected_item = QTableWidgetItem(segment.corrected_text)
            raw_item = QTableWidgetItem(segment.raw_text)
            raw_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

            self.segment_table.setItem(row_index, 0, start_item)
            self.segment_table.setItem(row_index, 1, end_item)
            self.segment_table.setItem(row_index, 2, speaker_item)
            self.segment_table.setItem(row_index, 3, corrected_item)
            self.segment_table.setItem(row_index, 4, raw_item)
        self._sync_correction_controls(bool(analysis.segments))

    def _emit_corrections(self) -> None:
        if self._current_analysis is None:
            return
        source_segments = {item.segment_id: item for item in self._current_analysis.segments}
        edited_segments: list[TranscriptAnalysisSegment] = []
        for row_index in range(self.segment_table.rowCount()):
            id_item = self.segment_table.item(row_index, 0)
            speaker_item = self.segment_table.item(row_index, 2)
            corrected_item = self.segment_table.item(row_index, 3)
            if id_item is None or speaker_item is None or corrected_item is None:
                continue
            segment_id = str(id_item.data(Qt.ItemDataRole.UserRole))
            source = source_segments.get(segment_id)
            if source is None:
                continue
            edited_segments.append(
                replace(
                    source,
                    speaker=speaker_item.text().strip() or source.speaker,
                    corrected_text=corrected_item.text().strip() or source.corrected_text,
                )
            )
        if edited_segments:
            self.analysis_corrections_requested.emit(self._current_analysis.transcript_id, edited_segments)

    def _rename_selected_speaker_everywhere(self) -> None:
        row_index = self.segment_table.currentRow()
        target_speaker = self.speaker_bulk_edit.text().strip()
        if row_index < 0 or not target_speaker:
            return
        source_item = self.segment_table.item(row_index, 2)
        if source_item is None:
            return
        source_speaker = source_item.text().strip()
        if not source_speaker:
            return
        for candidate_row in range(self.segment_table.rowCount()):
            speaker_item = self.segment_table.item(candidate_row, 2)
            if speaker_item is not None and speaker_item.text().strip() == source_speaker:
                speaker_item.setText(target_speaker)

    def _apply_speaker_to_selection(self) -> None:
        target_speaker = self.speaker_bulk_edit.text().strip()
        if not target_speaker:
            return
        selected_rows = sorted({index.row() for index in self.segment_table.selectionModel().selectedRows()})
        for row_index in selected_rows:
            speaker_item = self.segment_table.item(row_index, 2)
            if speaker_item is not None:
                speaker_item.setText(target_speaker)

    def _move_selected_segment(self, direction: int) -> None:
        current_row = self.segment_table.currentRow()
        if current_row < 0:
            return
        target_row = current_row + direction
        if target_row < 0 or target_row >= self.segment_table.rowCount():
            return
        self._swap_rows(current_row, target_row)
        self.segment_table.selectRow(target_row)

    def _merge_selected_with_next(self) -> None:
        current_row = self.segment_table.currentRow()
        if current_row < 0 or current_row >= self.segment_table.rowCount() - 1:
            return
        current_end_item = self.segment_table.item(current_row, 1)
        next_end_item = self.segment_table.item(current_row + 1, 1)
        current_speaker_item = self.segment_table.item(current_row, 2)
        next_speaker_item = self.segment_table.item(current_row + 1, 2)
        current_corrected_item = self.segment_table.item(current_row, 3)
        next_corrected_item = self.segment_table.item(current_row + 1, 3)
        current_raw_item = self.segment_table.item(current_row, 4)
        next_raw_item = self.segment_table.item(current_row + 1, 4)
        if not all(
            item is not None
            for item in (
                current_end_item,
                next_end_item,
                current_speaker_item,
                next_speaker_item,
                current_corrected_item,
                next_corrected_item,
                current_raw_item,
                next_raw_item,
            )
        ):
            return

        current_end_item.setText(next_end_item.text())
        current_speaker_item.setText(current_speaker_item.text().strip() or next_speaker_item.text().strip())
        current_corrected_item.setText(
            self._join_segment_text(current_corrected_item.text(), next_corrected_item.text())
        )
        current_raw_item.setText(self._join_segment_text(current_raw_item.text(), next_raw_item.text()))
        self.segment_table.removeRow(current_row + 1)
        self.segment_table.selectRow(current_row)
        self._sync_correction_controls(self.segment_table.rowCount() > 0)

    def _populate_graph(self, nodes: list[GraphNode], transcripts: list[Transcript]) -> None:
        self.graph_tree.clear()
        if not nodes:
            placeholder = QTreeWidgetItem(["No graph nodes yet.", "", "", ""])
            self.graph_tree.addTopLevelItem(placeholder)
            return

        transcript_texts = {transcript.id: transcript.text for transcript in transcripts}
        nodes_by_id = {node.id: node for node in nodes}
        children_map: dict[int, list[GraphNode]] = defaultdict(list)
        roots: list[GraphNode] = []
        orphans: list[GraphNode] = []

        for node in nodes:
            if node.branch_type == "root" and node.parent_node_id is None:
                roots.append(node)
            elif node.parent_node_id is not None and node.parent_node_id in nodes_by_id:
                children_map[node.parent_node_id].append(node)
            else:
                orphans.append(node)

        def child_sort_key(node: GraphNode) -> tuple[int, int, int]:
            if node.branch_type == "main":
                return (0, 0, node.id)
            return (1, node.branch_slot or 0, node.id)

        def add_node(parent: QTreeWidget | QTreeWidgetItem, node: GraphNode) -> None:
            transcript_text = transcript_texts.get(node.transcript_id, "No transcript linked")
            item = QTreeWidgetItem(
                [
                    node.node_text,
                    self._branch_label(node),
                    self._truncate(transcript_text, 72),
                    node.created_at,
                ]
            )
            item.setToolTip(0, node.node_text)
            item.setToolTip(2, transcript_text)
            if node.override_reason:
                item.setToolTip(1, f"{self._branch_label(node)}\n{node.override_reason}")
            if isinstance(parent, QTreeWidget):
                parent.addTopLevelItem(item)
            else:
                parent.addChild(item)
            for child in sorted(children_map.get(node.id, []), key=child_sort_key):
                add_node(item, child)

        for root in sorted(roots, key=lambda node: node.id):
            add_node(self.graph_tree, root)

        if orphans:
            orphan_bucket = QTreeWidgetItem(["Unlinked", "", "", ""])
            orphan_bucket.setToolTip(0, "Nodes with missing or invalid parent references.")
            self.graph_tree.addTopLevelItem(orphan_bucket)
            for orphan in sorted(orphans, key=child_sort_key):
                add_node(orphan_bucket, orphan)

        self.graph_tree.expandAll()

    def _populate_snapshots(self, snapshots: list[Snapshot]) -> None:
        self.snapshot_table.setRowCount(0)
        if not snapshots:
            self.snapshot_table.setRowCount(1)
            self.snapshot_table.setItem(0, 0, QTableWidgetItem("No snapshots available."))
            self.snapshot_table.setItem(0, 1, QTableWidgetItem(""))
            self.snapshot_table.setItem(0, 2, QTableWidgetItem(""))
            self.snapshot_table.setItem(0, 3, QTableWidgetItem(""))
            return

        for row_index, snapshot in enumerate(snapshots):
            self.snapshot_table.insertRow(row_index)
            short_hash = f"{snapshot.hash_sha256[:12]}..."
            values = [
                snapshot.created_at,
                str(snapshot.node_count),
                short_hash,
                snapshot.hash_sha256,
            ]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column_index in {2, 3}:
                    item.setToolTip(snapshot.hash_sha256)
                self.snapshot_table.setItem(row_index, column_index, item)

    @staticmethod
    def _quality_summary(analysis: TranscriptAnalysis) -> str:
        report = analysis.quality_report
        if report is None:
            return "No quality report available."
        warnings = " | ".join(report.warnings) if report.warnings else "No warnings"
        return (
            f"{report.speaker_count} speakers  |  overlap {report.overlap_ratio:.2f}  |  "
            f"coverage {report.word_timing_coverage:.2f}  |  {warnings}"
        )

    @staticmethod
    def _branch_label(node: GraphNode) -> str:
        if node.branch_type == "side":
            return f"side-{node.branch_slot}"
        return node.branch_type

    @staticmethod
    def _truncate(value: str, limit: int) -> str:
        if len(value) <= limit:
            return value
        return value[: limit - 3] + "..."

    @staticmethod
    def _format_seconds(value: float) -> str:
        total_milliseconds = max(0, int(round(value * 1000)))
        minutes, remainder = divmod(total_milliseconds, 60_000)
        seconds, milliseconds = divmod(remainder, 1_000)
        return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

    def _swap_rows(self, first_row: int, second_row: int) -> None:
        column_count = self.segment_table.columnCount()
        first_items = [self._clone_table_item(self.segment_table.item(first_row, column)) for column in range(column_count)]
        second_items = [self._clone_table_item(self.segment_table.item(second_row, column)) for column in range(column_count)]
        for column_index in range(column_count):
            self.segment_table.setItem(first_row, column_index, second_items[column_index])
            self.segment_table.setItem(second_row, column_index, first_items[column_index])

    @staticmethod
    def _clone_table_item(item: QTableWidgetItem | None) -> QTableWidgetItem:
        if item is None:
            return QTableWidgetItem("")
        clone = QTableWidgetItem(item)
        clone.setData(Qt.ItemDataRole.UserRole, item.data(Qt.ItemDataRole.UserRole))
        return clone

    @staticmethod
    def _join_segment_text(first: str, second: str) -> str:
        parts = [part.strip() for part in (first, second) if part and part.strip()]
        return " ".join(parts)

    def _sync_correction_controls(self, enabled: bool) -> None:
        self.speaker_bulk_edit.setEnabled(enabled)
        self.rename_speaker_button.setEnabled(enabled)
        self.apply_speaker_to_selection_button.setEnabled(enabled)
        self.move_segment_up_button.setEnabled(enabled)
        self.move_segment_down_button.setEnabled(enabled)
        self.merge_next_button.setEnabled(enabled)
