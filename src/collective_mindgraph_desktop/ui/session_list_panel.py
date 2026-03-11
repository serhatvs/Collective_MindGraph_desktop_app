"""Session explorer panel."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from ..models import Session
from .widgets import CardWidget, EmptyStateWidget


class SessionListPanel(QWidget):
    search_changed = Signal(str)
    new_session_requested = Signal()
    delete_session_requested = Signal(int)
    session_selected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        card = CardWidget("Session Explorer")
        layout.addWidget(card)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by title or device ID")
        self.search_input.textChanged.connect(self.search_changed.emit)
        card.body_layout.addWidget(self.search_input)

        button_row = QHBoxLayout()
        self.new_button = QPushButton("New Session")
        self.delete_button = QPushButton("Delete")
        self.delete_button.setProperty("secondary", True)
        self.delete_button.setEnabled(False)

        self.new_button.clicked.connect(self.new_session_requested.emit)
        self.delete_button.clicked.connect(self._confirm_delete)

        button_row.addWidget(self.new_button)
        button_row.addWidget(self.delete_button)
        card.body_layout.addLayout(button_row)

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._handle_current_item_changed)

        self.empty_state = EmptyStateWidget(
            "No sessions",
            "Create a session or seed demo data to start exploring reasoning timelines.",
        )

        self.stack_host = QWidget()
        self.stack_layout = QStackedLayout(self.stack_host)
        self.stack_layout.setContentsMargins(0, 0, 0, 0)
        self.stack_layout.addWidget(self.empty_state)
        self.stack_layout.addWidget(self.list_widget)
        card.body_layout.addWidget(self.stack_host)

        self._sessions_by_id: dict[int, Session] = {}

    def set_sessions(self, sessions: list[Session], selected_id: int | None = None) -> None:
        self._sessions_by_id = {session.id: session for session in sessions}
        self.list_widget.blockSignals(True)
        self.list_widget.clear()

        for session in sessions:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, session.id)
            item.setText(
                f"{session.title}\n"
                f"{session.device_id}  |  {session.status.upper()}  |  Updated {session.updated_at}"
            )
            item.setToolTip(
                f"{session.title}\nDevice: {session.device_id}\nStatus: {session.status}\n"
                f"Created: {session.created_at}\nUpdated: {session.updated_at}"
            )
            self.list_widget.addItem(item)

        self.stack_layout.setCurrentWidget(self.list_widget if sessions else self.empty_state)

        item_to_select: QListWidgetItem | None = None
        if selected_id is not None:
            for index in range(self.list_widget.count()):
                candidate = self.list_widget.item(index)
                if int(candidate.data(Qt.ItemDataRole.UserRole)) == selected_id:
                    item_to_select = candidate
                    break
        if item_to_select is not None:
            self.list_widget.setCurrentItem(item_to_select)
        self.list_widget.blockSignals(False)

        self.delete_button.setEnabled(item_to_select is not None)
        if item_to_select is not None:
            self.session_selected.emit(int(item_to_select.data(Qt.ItemDataRole.UserRole)))

    def current_session_id(self) -> int | None:
        current_item = self.list_widget.currentItem()
        if current_item is None:
            return None
        return int(current_item.data(Qt.ItemDataRole.UserRole))

    def search_text(self) -> str:
        return self.search_input.text()

    def set_search_text(self, text: str) -> None:
        self.search_input.setText(text)

    def _handle_current_item_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        self.delete_button.setEnabled(current is not None)
        if current is not None:
            self.session_selected.emit(int(current.data(Qt.ItemDataRole.UserRole)))

    def _confirm_delete(self) -> None:
        session_id = self.current_session_id()
        if session_id is None:
            return
        session = self._sessions_by_id.get(session_id)
        session_name = session.title if session else "this session"
        result = QMessageBox.question(
            self,
            "Delete Session",
            f"Delete '{session_name}' and all related transcripts, graph nodes, and snapshots?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result == QMessageBox.StandardButton.Yes:
            self.delete_session_requested.emit(session_id)
