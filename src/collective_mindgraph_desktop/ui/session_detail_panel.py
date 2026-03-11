"""Session detail area."""

from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models import GraphNode, SessionDetail, Snapshot, Transcript
from .widgets import CardWidget


class SessionDetailPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
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
        self.transcript_card.body_layout.addWidget(self.transcript_list)
        content_layout.addWidget(self.transcript_card)

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
            return

        self._overview_labels["title"].setText(detail.session.title)
        self._overview_labels["device_id"].setText(detail.session.device_id)
        self._overview_labels["status"].setText(detail.session.status.upper())
        self._overview_labels["created_at"].setText(detail.session.created_at)
        self._overview_labels["updated_at"].setText(detail.session.updated_at)
        self._overview_labels["transcript_count"].setText(str(len(detail.transcripts)))
        self._overview_labels["node_count"].setText(str(len(detail.graph_nodes)))
        self._overview_labels["snapshot_count"].setText(str(len(detail.snapshots)))

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
                f"{transcript.created_at}  |  Confidence {transcript.confidence:.2f}\n{transcript.text}"
            )
            item.setToolTip(transcript.text)
            self.transcript_list.addItem(item)

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
    def _branch_label(node: GraphNode) -> str:
        if node.branch_type == "side":
            return f"side-{node.branch_slot}"
        return node.branch_type

    @staticmethod
    def _truncate(value: str, limit: int) -> str:
        if len(value) <= limit:
            return value
        return value[: limit - 3] + "..."
