"""Review Queue page for human-in-the-loop validation of AI extractions."""

from __future__ import annotations

import json
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QMessageBox,
    QInputDialog,
)

from ...models import SessionDetail
from ..widgets import EmptyStateWidget


class ReviewQueuePage(QWidget):
    node_approved = Signal(str) # node_id
    node_rejected = Signal(str, str) # node_id, reason
    node_edited = Signal(str, str) # node_id, new_text

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        
        header = QLabel("Pending Knowledge Suggestions")
        header.setStyleSheet("font-size: 14pt; font-weight: bold; color: #264a7f;")
        layout.addWidget(header)
        
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Type", "Confidence", "Suggestion", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.empty_state = EmptyStateWidget(
            "No pending review suggestions yet.",
            "This page shows extracted memory items that still need human review before they become trusted memory.\n\n"
            "To populate it:\n"
            "- Open or import a session with extracted memory\n"
            "- Transcribe a local file\n"
            "- Or use Tools > Seed Technical Demo\n\n"
            "If you already reviewed everything, check Reviewed Memory or Knowledge Graph.",
        )
        layout.addWidget(self.empty_state, 1)
        self.table.hide()
        
        self._all_nodes = []

    def update_pending_data(self, nodes: list[dict]) -> None:
        self._all_nodes = nodes
        self.table.setRowCount(0)
        
        # Filter for pending
        pending = []
        for n in nodes:
            meta_str = n.get("metadata_json") or "{}"
            meta = json.loads(meta_str) if isinstance(meta_str, str) else meta_str
            if meta.get("review_status") == "pending":
                pending.append(n)

        if not pending:
            self.table.hide()
            self.empty_state.show()
            return

        self.empty_state.hide()
        self.table.show()
        
        for node in pending:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            self.table.setItem(row, 0, QTableWidgetItem(str(node.get("type"))))
            
            # Confidence from metadata or 1.0
            meta_str = node.get("metadata_json") or "{}"
            meta = json.loads(meta_str) if isinstance(meta_str, str) else meta_str
            conf = meta.get("confidence", 1.0)
            self.table.setItem(row, 1, QTableWidgetItem(f"{conf:.2f}"))
            
            title = node.get("title") or node.get("text_content") or ""
            self.table.setItem(row, 2, QTableWidgetItem(str(title)))
            
            # Actions
            btn_container = QWidget()
            btn_layout = QHBoxLayout(btn_container)
            btn_layout.setContentsMargins(2, 2, 2, 2)
            
            approve_btn = QPushButton("Approve")
            approve_btn.setStyleSheet("background: #dcfce7; color: #166534;")
            approve_btn.clicked.connect(lambda checked=False, nid=node["id"]: self.node_approved.emit(nid))
            
            reject_btn = QPushButton("Reject")
            reject_btn.setStyleSheet("background: #fee2e2; color: #991b1b;")
            reject_btn.clicked.connect(lambda checked=False, nid=node["id"]: self._handle_reject(nid))
            
            btn_layout.addWidget(approve_btn)
            btn_layout.addWidget(reject_btn)
            
            self.table.setCellWidget(row, 3, btn_container)
            # Store ID in hidden column if needed or first column
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, node["id"])

    def _handle_reject(self, node_id: str):
        reason, ok = QInputDialog.getText(self, "Reject Suggestion", "Reason for rejection:")
        if ok:
            self.node_rejected.emit(node_id, reason)
