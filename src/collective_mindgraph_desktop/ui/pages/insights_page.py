"""Insights page showing Tasks, Decisions, and Topics."""

from __future__ import annotations

import json
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
from ..widgets import CardWidget, EmptyStateWidget

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
        
        # 4. Entities Card
        self.entities_card = CardWidget("Entities")
        self.entities_list = QListWidget()
        self.entities_list.setStyleSheet("QListWidget::item { padding: 8px; }")
        self.entities_list.itemDoubleClicked.connect(self._edit_item)
        self.entities_card.body_layout.addWidget(self.entities_list)
        self.container_layout.addWidget(self.entities_card)
        
        # 5. Risks Card
        self.risks_card = CardWidget("Risks")
        self.risks_list = QListWidget()
        self.risks_list.setStyleSheet("QListWidget::item { padding: 8px; }")
        self.risks_list.itemDoubleClicked.connect(self._edit_item)
        self.risks_card.body_layout.addWidget(self.risks_list)
        self.container_layout.addWidget(self.risks_card)
        
        # 6. Open Questions Card
        self.open_qs_card = CardWidget("Open Questions")
        self.open_qs_list = QListWidget()
        self.open_qs_list.setStyleSheet("QListWidget::item { padding: 8px; }")
        self.open_qs_list.itemDoubleClicked.connect(self._edit_item)
        self.open_qs_card.body_layout.addWidget(self.open_qs_list)
        self.container_layout.addWidget(self.open_qs_card)
        
        # 7. Follow-ups Card
        self.followups_card = CardWidget("Follow-ups")
        self.followups_list = QListWidget()
        self.followups_list.setStyleSheet("QListWidget::item { padding: 8px; }")
        self.followups_list.itemDoubleClicked.connect(self._edit_item)
        self.followups_card.body_layout.addWidget(self.followups_list)
        self.container_layout.addWidget(self.followups_card)

        self.empty_state = EmptyStateWidget(
            "No extracted notes yet.",
            "This page shows the basic tasks, decisions, topics, and follow-ups extracted from the selected session.\n\n"
            "To populate it:\n"
            "- Open or import a session with extracted memory\n"
            "- Transcribe a local file\n"
            "- Or use Tools > Seed Technical Demo\n\n"
            "Items marked pending still need human review before they are trusted memory.",
        )
        self.container_layout.addWidget(self.empty_state, 1)

        self._review_cards = (
            self.tasks_card,
            self.decisions_card,
            self.topics_card,
            self.entities_card,
            self.risks_card,
            self.open_qs_card,
            self.followups_card,
        )
        self._set_review_content_visible(False)
        
        self.container_layout.addStretch(1)

    def _edit_item(self, item: QListWidgetItem) -> None:
        current_text = item.text()
        
        # Determine type from visible prefix.
        item_type = "task"
        prefix_map = {
            "Task: ": "task",
            "Decision: ": "decision",
            "Topic: ": "topic",
            "Entity: ": "entity",
            "Risk: ": "risk",
            "Question: ": "open_question",
            "Follow-up: ": "follow_up",
        }
        for prefix, mapped_type in prefix_map.items():
            if current_text.startswith(prefix):
                item_type = mapped_type
                break

        # Strip prefix and review suffix for clean edit.
        clean_text = current_text
        for prefix in prefix_map:
            if clean_text.startswith(prefix):
                clean_text = clean_text[len(prefix):]
                break
        pending_suffix = " [pending review]"
        if clean_text.endswith(pending_suffix):
            clean_text = clean_text[: -len(pending_suffix)]
        
        # If task, strip resp suffix (Resp: ...)
        resp_index = clean_text.find(" (Resp:")
        resp_suffix = clean_text[resp_index:] if resp_index != -1 else ""
        if resp_index != -1:
            clean_text = clean_text[:resp_index]

        new_text, ok = QInputDialog.getText(self, "Edit Knowledge Item", "Update text:", text=clean_text)
        if ok and new_text and new_text != clean_text:
            self.knowledge_item_updated.emit(item_type, clean_text, new_text)
            # Optimistically update UI
            prefix = next((prefix for prefix in prefix_map if current_text.startswith(prefix)), "")
            item.setText(f"{prefix}{new_text}{resp_suffix}")

    def set_detail(self, detail: SessionDetail | None) -> None:
        self.tasks_list.clear()
        self.decisions_list.clear()
        self.topics_list.clear()
        self.entities_list.clear()
        self.risks_list.clear()
        self.open_qs_list.clear()
        self.followups_list.clear()
        self._set_review_content_visible(False)
        
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
        self.entities_list.clear()
        self.risks_list.clear()
        self.open_qs_list.clear()
        self.followups_list.clear()
        
        extracted = []
        for node in nodes:
            meta = self._metadata_for_node(node)
            status = str(meta.get("review_status") or "pending")
            if bool(meta.get("disabled")) or status in {"rejected", "merged"}:
                continue
            if node.get("type") in {"TASK", "DECISION", "TOPIC", "ENTITY", "RISK", "OPEN_QUESTION", "FOLLOW_UP"}:
                extracted.append((node, meta, status))

        self._set_review_content_visible(bool(extracted))
        
        for node, meta, status in extracted:
            title = node.get("title") or node.get("text_content") or ""
            if status == "pending":
                title = f"{title} [pending review]"
            n_type = node.get("type")
            
            if n_type == "TASK":
                item = QListWidgetItem(f"Task: {title}")
                if meta.get("assignee"):
                    item.setText(f"{item.text()} (Resp: {meta['assignee']})")
                self.tasks_list.addItem(item)
            elif n_type == "DECISION":
                self.decisions_list.addItem(QListWidgetItem(f"Decision: {title}"))
            elif n_type == "TOPIC":
                self.topics_list.addItem(QListWidgetItem(f"Topic: {title}"))
            elif n_type == "ENTITY":
                self.entities_list.addItem(QListWidgetItem(f"Entity: {title}"))
            elif n_type == "RISK":
                self.risks_list.addItem(QListWidgetItem(f"Risk: {title}"))
            elif n_type == "OPEN_QUESTION":
                self.open_qs_list.addItem(QListWidgetItem(f"Question: {title}"))
            elif n_type == "FOLLOW_UP":
                self.followups_list.addItem(QListWidgetItem(f"Follow-up: {title}"))

    def _set_review_content_visible(self, has_reviewed_items: bool) -> None:
        for card in self._review_cards:
            card.setVisible(has_reviewed_items)
        self.empty_state.setVisible(not has_reviewed_items)

    @staticmethod
    def _metadata_for_node(node: dict) -> dict:
        raw = node.get("metadata_json") or {}
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}
