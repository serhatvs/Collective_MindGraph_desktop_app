"""Insights page showing reviewed tasks, decisions, topics, and related items."""

from __future__ import annotations

import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...models import SessionDetail
from ..widgets import CardWidget


class InsightsPage(QWidget):
    knowledge_item_updated = Signal(str, str, str)

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

        self.tasks_list = self._add_list_card("Tasks")
        self.decisions_list = self._add_list_card("Decisions")
        self.topics_list = self._add_list_card("Topics")
        self.entities_list = self._add_list_card("Entities")
        self.risks_list = self._add_list_card("Risks")
        self.open_qs_list = self._add_list_card("Open Questions")
        self.followups_list = self._add_list_card("Follow-ups")

        self.container_layout.addStretch(1)
        self._show_empty_rows()

    def _add_list_card(self, title: str) -> QListWidget:
        card = CardWidget(title)
        list_widget = QListWidget()
        list_widget.setStyleSheet("QListWidget::item { padding: 8px; }")
        list_widget.itemDoubleClicked.connect(self._edit_item)
        card.body_layout.addWidget(list_widget)
        self.container_layout.addWidget(card)
        return list_widget

    def _edit_item(self, item: QListWidgetItem) -> None:
        payload = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(payload, dict) or payload.get("empty"):
            return

        item_type = str(payload.get("type") or "task")
        clean_text = str(payload.get("text") or item.text())
        new_text, ok = QInputDialog.getText(self, "Edit Knowledge Item", "Update text:", text=clean_text)
        if ok and new_text and new_text != clean_text:
            self.knowledge_item_updated.emit(item_type, clean_text, new_text)
            payload["text"] = new_text
            item.setData(Qt.ItemDataRole.UserRole, payload)
            item.setText(self._display_text(new_text, payload))

    def set_detail(self, detail: SessionDetail | None) -> None:
        self._clear_lists()
        self._show_empty_rows()

    def update_reviewed_data(self, nodes: list[dict]) -> None:
        self._clear_lists()

        reviewed = []
        for node in nodes:
            meta = self._metadata(node)
            if meta.get("review_status") in ("approved", "edited"):
                reviewed.append((node, meta))

        if not reviewed:
            self._show_empty_rows()
            return

        for node, meta in reviewed:
            title = str(node.get("title") or node.get("text_content") or "")
            node_type = str(node.get("type") or "")
            payload = {
                "type": node_type.lower(),
                "text": title,
                "assignee": meta.get("assignee"),
            }
            item = QListWidgetItem(self._display_text(title, payload))
            item.setData(Qt.ItemDataRole.UserRole, payload)
            target = self._list_for_type(node_type)
            if target is not None:
                target.addItem(item)

        self._fill_empty_lists()

    def _clear_lists(self) -> None:
        for list_widget in self._all_lists():
            list_widget.clear()

    def _show_empty_rows(self) -> None:
        labels = {
            self.tasks_list: "No reviewed tasks yet.",
            self.decisions_list: "No reviewed decisions yet.",
            self.topics_list: "No reviewed topics yet.",
            self.entities_list: "No reviewed entities yet.",
            self.risks_list: "No reviewed risks yet.",
            self.open_qs_list: "No reviewed open questions yet.",
            self.followups_list: "No reviewed follow-ups yet.",
        }
        for list_widget, text in labels.items():
            self._add_empty_item(list_widget, text)

    def _fill_empty_lists(self) -> None:
        for list_widget in self._all_lists():
            if list_widget.count() == 0:
                self._add_empty_item(list_widget, "No reviewed items in this category.")

    def _add_empty_item(self, list_widget: QListWidget, text: str) -> None:
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, {"empty": True})
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        list_widget.addItem(item)

    def _all_lists(self) -> list[QListWidget]:
        return [
            self.tasks_list,
            self.decisions_list,
            self.topics_list,
            self.entities_list,
            self.risks_list,
            self.open_qs_list,
            self.followups_list,
        ]

    def _list_for_type(self, node_type: str) -> QListWidget | None:
        return {
            "TASK": self.tasks_list,
            "DECISION": self.decisions_list,
            "TOPIC": self.topics_list,
            "ENTITY": self.entities_list,
            "RISK": self.risks_list,
            "OPEN_QUESTION": self.open_qs_list,
            "FOLLOW_UP": self.followups_list,
        }.get(node_type)

    @staticmethod
    def _display_text(title: str, payload: dict[str, object]) -> str:
        assignee = payload.get("assignee")
        return f"{title} (Resp: {assignee})" if assignee else title

    @staticmethod
    def _metadata(node: dict) -> dict:
        meta = node.get("metadata_json") or "{}"
        if isinstance(meta, str):
            try:
                return json.loads(meta)
            except json.JSONDecodeError:
                return {}
        return meta if isinstance(meta, dict) else {}
