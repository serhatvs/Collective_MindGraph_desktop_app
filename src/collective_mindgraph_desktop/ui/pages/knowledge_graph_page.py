"""Knowledge Graph page showing raw node and edge lists with interactive explorer."""

from __future__ import annotations

import json
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QTabWidget,
    QSplitter,
    QLineEdit,
    QComboBox,
    QTextEdit,
    QPushButton,
    QInputDialog,
    QMessageBox,
    QListWidget,
)

from ...models import SessionDetail
from ..widgets import CardWidget, EmptyStateWidget


class KnowledgeGraphPage(QWidget):
    source_trace_requested = Signal(str, str) # session_id, segment_id
    node_updated = Signal(str, dict) # node_id, properties
    node_merge_requested = Signal(str, str) # source_node_id, target_node_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        
        # 0. Toolbar
        toolbar = QHBoxLayout()
        self.search_filter = QLineEdit()
        self.search_filter.setPlaceholderText("Search nodes by title/content...")
        self.search_filter.textChanged.connect(self._apply_filters)
        
        self.type_filter = QComboBox()
        self.type_filter.addItems([
            "All Types",
            "SESSION",
            "SEGMENT",
            "TASK",
            "DECISION",
            "TOPIC",
            "ENTITY",
            "PERSON",
            "RISK",
            "OPEN_QUESTION",
            "FOLLOW_UP",
        ])
        self.type_filter.currentIndexChanged.connect(self._apply_filters)
        
        toolbar.addWidget(QLabel("Filter:"))
        toolbar.addWidget(self.search_filter, 1)
        toolbar.addWidget(self.type_filter)
        layout.addLayout(toolbar)
        
        # 1. Main View (Splitter)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(self.splitter, 1)

        self.empty_state = EmptyStateWidget(
            "No knowledge graph items yet.",
            "This page shows structured memory relationships after sessions are processed and reviewed.\n\n"
            "To populate it:\n"
            "- Open or import a session with extracted memory\n"
            "- Review pending items in Review Suggestions\n"
            "- Transcribe a local file\n"
            "- Or use Tools > Seed Technical Demo\n\n"
            "Graph items may include tasks, decisions, topics, entities, risks, open questions, and follow-ups.",
        )
        layout.addWidget(self.empty_state, 1)
        
        # Tables Container
        self.tabs = QTabWidget()
        self.splitter.addWidget(self.tabs)
        
        # Nodes Tab
        self.nodes_tab = QWidget()
        nodes_layout = QVBoxLayout(self.nodes_tab)
        nodes_layout.setContentsMargins(0, 0, 0, 0)
        self.nodes_table = QTableWidget(0, 4)
        self.nodes_table.setHorizontalHeaderLabels(["ID", "Type", "Status", "Title/Content"])
        self.nodes_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.nodes_table.itemSelectionChanged.connect(self._handle_node_selection)
        nodes_layout.addWidget(self.nodes_table)
        self.tabs.addTab(self.nodes_tab, "Graph Nodes")
        
        # Edges Tab
        self.edges_tab = QWidget()
        edges_layout = QVBoxLayout(self.edges_tab)
        edges_layout.setContentsMargins(0, 0, 0, 0)
        self.edges_table = QTableWidget(0, 4)
        self.edges_table.setHorizontalHeaderLabels(["Source ID", "Type", "Target ID", "Confidence"])
        self.edges_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        edges_layout.addWidget(self.edges_table)
        self.tabs.addTab(self.edges_tab, "Graph Edges")
        
        # 2. Detail Panel (Splitter Lower Part)
        detail_container = QWidget()
        detail_main_layout = QHBoxLayout(detail_container)
        detail_main_layout.setContentsMargins(0, 0, 0, 0)
        detail_main_layout.setSpacing(20)
        self.splitter.addWidget(detail_container)
        
        # Properties Card
        self.detail_panel = CardWidget("Node Properties")
        detail_main_layout.addWidget(self.detail_panel, 1)
        
        prop_layout = QVBoxLayout()
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setStyleSheet("font-family: 'Consolas', monospace; font-size: 9pt;")
        prop_layout.addWidget(self.detail_text)
        
        actions_row = QHBoxLayout()
        self.trace_button = QPushButton("Open Source Trace")
        self.trace_button.setEnabled(False)
        self.trace_button.clicked.connect(self._handle_trace_click)
        
        self.edit_button = QPushButton("Edit Node")
        self.edit_button.setEnabled(False)
        self.edit_button.clicked.connect(self._handle_edit_click)
        
        self.disable_button = QPushButton("Disable Node")
        self.disable_button.setEnabled(False)
        self.disable_button.clicked.connect(self._handle_disable_click)

        self.merge_button = QPushButton("Merge Into...")
        self.merge_button.setEnabled(False)
        self.merge_button.clicked.connect(self._handle_merge_click)
        
        actions_row.addWidget(self.trace_button)
        actions_row.addWidget(self.edit_button)
        actions_row.addWidget(self.disable_button)
        actions_row.addWidget(self.merge_button)
        prop_layout.addLayout(actions_row)
        self.detail_panel.body_layout.addLayout(prop_layout)
        
        # Neighbors Card
        self.neighbors_card = CardWidget("Related Nodes")
        detail_main_layout.addWidget(self.neighbors_card, 1)
        
        self.neighbors_list = QListWidget()
        self.neighbors_list.setStyleSheet("QListWidget::item { padding: 8px; border-bottom: 1px solid #f1f5f9; }")
        self.neighbors_card.body_layout.addWidget(self.neighbors_list)
        
        self.splitter.setSizes([500, 400])
        
        self._all_nodes = []
        self._all_edges = []
        self._selected_node = None
        self.splitter.hide()

    def update_graph_data(self, nodes: list[dict], edges: list[dict]) -> None:
        self._all_nodes = nodes
        self._all_edges = edges
        self._clear_selection_detail()
        has_graph_items = bool(nodes or edges)
        self.splitter.setVisible(has_graph_items)
        self.empty_state.setVisible(not has_graph_items)
        if not has_graph_items:
            self.nodes_table.setRowCount(0)
            self.edges_table.setRowCount(0)
            return

        self._apply_filters()
        
        self.edges_table.setRowCount(0)
        for edge in edges:
            row = self.edges_table.rowCount()
            self.edges_table.insertRow(row)
            self.edges_table.setItem(row, 0, QTableWidgetItem(str(edge.get("source_node_id"))))
            self.edges_table.setItem(row, 1, QTableWidgetItem(str(edge.get("edge_type"))))
            self.edges_table.setItem(row, 2, QTableWidgetItem(str(edge.get("target_node_id"))))
            self.edges_table.setItem(row, 3, QTableWidgetItem(f"{edge.get('confidence', 1.0):.2f}"))

    def _apply_filters(self) -> None:
        search_text = self.search_filter.text().lower()
        selected_type = self.type_filter.currentText()
        
        self.nodes_table.setRowCount(0)
        for node in self._all_nodes:
            n_type = str(node.get("type"))
            title = node.get("title") or node.get("text_content") or ""
            
            meta = self._node_metadata(node)
            status = "DISABLED" if meta.get("disabled") else "ACTIVE"
            
            if selected_type != "All Types" and n_type != selected_type:
                continue
            if search_text and search_text not in str(title).lower():
                continue
                
            row = self.nodes_table.rowCount()
            self.nodes_table.insertRow(row)
            self.nodes_table.setItem(row, 0, QTableWidgetItem(str(node.get("id"))))
            self.nodes_table.setItem(row, 1, QTableWidgetItem(n_type))
            self.nodes_table.setItem(row, 2, QTableWidgetItem(status))
            self.nodes_table.setItem(row, 3, QTableWidgetItem(str(title)[:150]))
            
            # Coloring
            if status == "DISABLED":
                for col in range(4):
                    self.nodes_table.item(row, col).setForeground(Qt.GlobalColor.gray)
            
            # Store full node in item for retrieval
            self.nodes_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, node)

        if self.nodes_table.rowCount() == 0:
            self._clear_selection_detail()

    def _handle_node_selection(self) -> None:
        selected_items = self.nodes_table.selectedItems()
        if not selected_items:
            self._clear_selection_detail()
            return
            
        row = selected_items[0].row()
        node = self.nodes_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        self._selected_node = node
        
        if not node: return
        
        meta = self._node_metadata(node)
        
        info = [
            f"Node ID: {node.get('id')}",
            f"Type:    {node.get('type')}",
            f"Created: {node.get('created_at')}",
            f"Updated: {node.get('updated_at')}",
            "\n[TITLE/CONTENT]",
            str(node.get('title') or node.get('text_content')),
            "\n[FULL METADATA]",
            json.dumps(meta, indent=2, ensure_ascii=False)
        ]
        self.detail_text.setText("\n".join(info))
        
        # Update buttons
        self.trace_button.setEnabled(True)
        self.edit_button.setEnabled(True)
        self.disable_button.setEnabled(True)
        self.merge_button.setEnabled(True)
        self.disable_button.setText("Enable Node" if meta.get("disabled") else "Disable Node")
        
        # Update Neighbors
        self._refresh_neighbors(node.get('id'))

    def _refresh_neighbors(self, node_id: str) -> None:
        self.neighbors_list.clear()
        
        # Outgoing edges
        for edge in self._all_edges:
            if edge.get("source_node_id") == node_id:
                target_id = edge.get("target_node_id")
                # Find target node title
                target_title = target_id
                for n in self._all_nodes:
                    if n.get("id") == target_id:
                        target_title = n.get("title") or n.get("text_content") or target_id
                        break
                self.neighbors_list.addItem(f"OUT [{edge.get('edge_type')}] to: {target_title}")
                
            elif edge.get("target_node_id") == node_id:
                source_id = edge.get("source_node_id")
                # Find source node title
                source_title = source_id
                for n in self._all_nodes:
                    if n.get("id") == source_id:
                        source_title = n.get("title") or n.get("text_content") or source_id
                        break
                self.neighbors_list.addItem(f"IN [{edge.get('edge_type')}] from: {source_title}")

    def _handle_trace_click(self) -> None:
        if not self._selected_node: return
        meta = self._node_metadata(self._selected_node)
        session_id = self._selected_node.get("source_session_id") or meta.get("source_session_id")
        segment_id = self._selected_node.get("source_segment_id") or meta.get("source_segment_id")

        if not segment_id and self._selected_node.get("type") == "SEGMENT":
            segment_id = self._fallback_segment_id_from_node_id(str(self._selected_node.get("id") or ""))

        if session_id or segment_id:
            self.source_trace_requested.emit(str(session_id or ""), str(segment_id or ""))

    def _handle_edit_click(self) -> None:
        if not self._selected_node: return
        current_text = self._selected_node.get("title") or self._selected_node.get("text_content") or ""
        new_text, ok = QInputDialog.getText(self, "Edit Node", "Update Title/Content:", text=current_text)
        if ok and new_text and new_text != current_text:
            props = {"title": new_text, "text_content": new_text, "edited_by_user": True}
            self.node_updated.emit(self._selected_node["id"], props)
            QMessageBox.information(self, "Node Updated", "Node changes will be persisted to the database.")

    def _handle_disable_click(self) -> None:
        if not self._selected_node: return
        meta = self._node_metadata(self._selected_node)
        
        is_disabled = meta.get("disabled", False)
        new_state = not is_disabled
        
        props = {"disabled": new_state}
        self.node_updated.emit(self._selected_node["id"], props)
        
        msg = "Node disabled. It will no longer appear in search results." if new_state else "Node enabled."
        QMessageBox.information(self, "Status Updated", msg)

    def _handle_merge_click(self) -> None:
        if not self._selected_node:
            return
        source_id = str(self._selected_node.get("id") or "")
        target_id, ok = QInputDialog.getText(self, "Merge Node", "Target node ID:")
        target_id = target_id.strip()
        if ok and target_id and target_id != source_id:
            self.node_merge_requested.emit(source_id, target_id)

    @staticmethod
    def _node_metadata(node: dict) -> dict:
        meta_str = node.get("metadata_json") or "{}"
        if isinstance(meta_str, dict):
            return meta_str
        try:
            parsed = json.loads(meta_str)
        except (TypeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _fallback_segment_id_from_node_id(node_id: str) -> str | None:
        if not node_id.startswith("seg_"):
            return None
        parts = node_id.split("_", 2)
        if len(parts) == 3 and parts[2]:
            return parts[2]
        return None

    def _clear_selection_detail(self) -> None:
        self._selected_node = None
        self.detail_text.clear()
        self.neighbors_list.clear()
        self.trace_button.setEnabled(False)
        self.edit_button.setEnabled(False)
        self.disable_button.setEnabled(False)
        self.merge_button.setEnabled(False)
