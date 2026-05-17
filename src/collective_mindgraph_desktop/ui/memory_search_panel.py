"""Global Memory Query / Search panel."""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QScrollArea,
    QFrame,
)

from ..transcription import (
    QueryResultItem,
    QueryResponse,
    RealtimeBackendTranscriptionConfig,
    RealtimeBackendTranscriptionService,
)
from .widgets import CardWidget, EmptyStateWidget

LOGGER = logging.getLogger(__name__)

class MemoryQueryWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        query: str,
        config: RealtimeBackendTranscriptionConfig,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._query = query
        self._config = config

    @Slot()
    def run(self) -> None:
        try:
            service = RealtimeBackendTranscriptionService(config=self._config)
            result = service.query_memory(self._query)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)


class MemorySearchPanel(QWidget):
    source_navigation_requested = Signal(str, str) # session_id, segment_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config: RealtimeBackendTranscriptionConfig | None = None
        self._query_thread: QThread | None = None
        self._query_worker: MemoryQueryWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.card = CardWidget("Memory Search")
        layout.addWidget(self.card)

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Ask a question or enter keywords...")
        self.search_input.returnPressed.connect(self._handle_search)
        
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self._handle_search)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)
        self.card.body_layout.addLayout(search_layout)

        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self._handle_item_double_clicked)
        self.card.body_layout.addWidget(self.results_list, 1)

        self.empty_state = EmptyStateWidget(
            "Search results will appear here",
            "Enter technical terms, tasks, or decisions to find context across sessions."
        )
        self.card.body_layout.addWidget(self.empty_state)
        self.results_list.hide()

    def set_config(self, config: RealtimeBackendTranscriptionConfig) -> None:
        self._config = config

    def _handle_search(self) -> None:
        query = self.search_input.text().strip()
        if not query or not self._config:
            return

        self.search_button.setEnabled(False)
        self.search_input.setEnabled(False)
        self.results_list.clear()
        self.empty_state.show()
        self.empty_state.setToolTip("Searching...")

        self._query_thread = QThread()
        self._query_worker = MemoryQueryWorker(query, self._config)
        self._query_worker.moveToThread(self._query_thread)
        
        self._query_thread.started.connect(self._query_worker.run)
        self._query_worker.finished.connect(self._handle_query_finished)
        self._query_worker.failed.connect(self._handle_query_failed)
        self._query_worker.finished.connect(self._query_thread.quit)
        self._query_worker.failed.connect(self._query_thread.quit)
        
        self._query_thread.start()

    def _handle_query_finished(self, response: QueryResponse) -> None:
        self.search_button.setEnabled(True)
        self.search_input.setEnabled(True)
        
        if not response.results:
            self.empty_state.show()
            self.results_list.hide()
            return

        self.empty_state.hide()
        self.results_list.show()

        for res in response.results:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, (res.source_session_id, res.source_segment_id))
            
            # Format text
            type_label = f"[{res.result_type.upper()}]"
            match_info = f" (Score: {res.score:.2f})"
            header = f"{type_label} {res.text}{match_info}"
            
            body = res.preview or ""
            if res.matched_terms:
                body += f"\nMatched: {', '.join(res.matched_terms)}"
            
            footer = f"Session: {res.source_session_id}"
            if res.timestamp:
                footer += f" | {res.timestamp}"
            
            item.setText(f"{header}\n{body}\n{footer}")
            self.results_list.addItem(item)

    def _handle_query_failed(self, error: str) -> None:
        self.search_button.setEnabled(True)
        self.search_input.setEnabled(True)
        self.empty_state.show()
        LOGGER.error("Memory query failed: %s", error)

    def _handle_item_double_clicked(self, item: QListWidgetItem) -> None:
        session_id, segment_id = item.data(Qt.ItemDataRole.UserRole)
        if session_id:
            self.source_navigation_requested.emit(str(session_id), str(segment_id or ""))
