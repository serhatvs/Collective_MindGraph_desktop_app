"""Insights page showing Tasks, Decisions, and Topics."""

from __future__ import annotations

import logging
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
    QScrollArea,
    QInputDialog,
)

from ...models import SessionDetail, TranscriptAnalysis
from ..widgets import CardWidget

class InsightsPage(QWidget):
    knowledge_item_updated = Signal(str, str, str) # item_type, original_text, new_text
    
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
        
        # 1. Tasks Card
        self.tasks_card = CardWidget("Tasks")
        self.tasks_list = QListWidget()
        self.tasks_list.setStyleSheet("QListWidget::item { padding: 8px; }")
        self.tasks_list.itemDoubleClicked.connect(self._edit_item)
        self.tasks_card.body_layout.addWidget(self.tasks_list)
        self.container_layout.addWidget(self.tasks_card)
        
        # 2. Decisions Card
        self.decisions_card = CardWidget("Decisions")
        self.decisions_list = QListWidget()
        self.decisions_list.setStyleSheet("QListWidget::item { padding: 8px; }")
        self.decisions_list.itemDoubleClicked.connect(self._edit_item)
        self.decisions_card.body_layout.addWidget(self.decisions_list)
        self.container_layout.addWidget(self.decisions_card)
        
        # 3. Topics Card
        self.topics_card = CardWidget("Topics")
        self.topics_list = QListWidget()
        self.topics_list.setStyleSheet("QListWidget::item { padding: 8px; }")
        self.topics_list.itemDoubleClicked.connect(self._edit_item)
        self.topics_card.body_layout.addWidget(self.topics_list)
        self.container_layout.addWidget(self.topics_card)
        
        self.container_layout.addStretch(1)

    def _edit_item(self, item: QListWidgetItem) -> None:
        current_text = item.text()
        
        # Determine type from prefix emoji
        item_type = "task"
        if current_text.startswith("💡 "): item_type = "decision"
        elif current_text.startswith("🏷️ "): item_type = "topic"
        
        # Strip emoji and resp for clean edit
        clean_text = current_text
        if current_text.startswith(("✅ ", "💡 ", "🏷️ ")):
            clean_text = current_text[2:]
        
        # If task, strip resp suffix (Resp: ...)
        resp_index = clean_text.find(" (Resp:")
        if resp_index != -1:
            clean_text = clean_text[:resp_index]

        new_text, ok = QInputDialog.getText(self, "Edit Knowledge Item", "Update text:", text=clean_text)
        if ok and new_text and new_text != clean_text:
            self.knowledge_item_updated.emit(item_type, clean_text, new_text)
            # Optimistically update UI
            prefix = current_text[:2] if current_text.startswith(("✅ ", "💡 ", "🏷️ ")) else ""
            suffix = current_text[resp_index:] if resp_index != -1 else ""
            item.setText(f"{prefix}{new_text}{suffix}")

    def set_detail(self, detail: SessionDetail | None) -> None:
        self.tasks_list.clear()
        self.decisions_list.clear()
        self.topics_list.clear()
        
        if not detail:
            return

        # Fetch V2 data to check review status
        # (This is a bit inefficient to fetch twice, but for prototype it works)
        # In real app, SessionDetail would include V2 graph nodes.
        pass

    def update_reviewed_data(self, nodes: list[dict]) -> None:
        self.tasks_list.clear()
        self.decisions_list.clear()
        self.topics_list.clear()
        
        # Filter for approved or edited
        reviewed = [n for n in nodes if n.get("metadata_json") and 
                   (json.loads(n["metadata_json"]) if isinstance(n["metadata_json"], str) else n["metadata_json"]).get("review_status") in ("approved", "edited")]
        
        for node in reviewed:
            meta_str = node.get("metadata_json") or "{}"
            meta = json.loads(meta_str) if isinstance(meta_str, str) else meta_str
            
            title = node.get("title") or node.get("text_content") or ""
            n_type = node.get("type")
            
            if n_type == "TASK":
                item = QListWidgetItem(f"✅ {title}")
                if meta.get("assignee"):
                    item.setText(f"{item.text()} (Resp: {meta['assignee']})")
                self.tasks_list.addItem(item)
            elif n_type == "DECISION":
                self.decisions_list.addItem(QListWidgetItem(f"💡 {title}"))
            elif n_type == "TOPIC":
                self.topics_list.addItem(QListWidgetItem(f"🏷️ {title}"))
