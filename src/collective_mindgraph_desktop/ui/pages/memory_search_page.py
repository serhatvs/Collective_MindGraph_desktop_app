"""Global Memory Search page with categorized results."""

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
)

from ...transcription import (
    QueryResultItem,
    QueryResponse,
    RealtimeBackendTranscriptionConfig,
    RealtimeBackendTranscriptionService,
)
from ..components.result_card import ResultCard
from ..widgets import CardWidget, EmptyStateWidget

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


class MemorySearchPage(QWidget):
    source_navigation_requested = Signal(str, str) # session_id, segment_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config: RealtimeBackendTranscriptionConfig | None = None
        self._query_thread: QThread | None = None
        self._query_worker: MemoryQueryWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        self.card = CardWidget("Knowledge Retrieval")
        layout.addWidget(self.card, 1)

        search_container = QWidget()
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search technical terms, tasks, or decisions across all meetings...")
        self.search_input.setMinimumHeight(44)
        self.search_input.setStyleSheet("font-size: 11pt; padding-left: 12px;")
        self.search_input.returnPressed.connect(self._handle_search)
        
        self.search_button = QPushButton("Search Memory")
        self.search_button.setMinimumHeight(44)
        self.search_button.setMinimumWidth(140)
        self.search_button.clicked.connect(self._handle_search)
        
        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(self.search_button)
        self.card.body_layout.addWidget(search_container)

        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self._handle_item_double_clicked)
        self.results_list.setSpacing(8)
        self.results_list.setStyleSheet("""
            QListWidget { border: none; background: transparent; }
            QListWidget::item { border-radius: 8px; }
        """)
        self.card.body_layout.addWidget(self.results_list, 1)

        self.empty_state = EmptyStateWidget(
            "Global Memory Search",
            "Enter keywords (e.g. 'FastAPI', 'kararlar') to find linked context from your entire session history."
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
        self.results_list.clear()
        self.empty_state.show()

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
        
        if not response.results:
            self.empty_state.show()
            self.results_list.hide()
            return

        self.empty_state.hide()
        self.results_list.show()

        for res in response.results:
            card = ResultCard()
            meta = f"Session: {res.source_session_id} | Score: {res.score:.2f}"
            card.set_result(res.result_type, res.text, res.preview, meta, res.matched_terms)
            
            item = QListWidgetItem(self.results_list)
            item.setSizeHint(card.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, (res.source_session_id, res.source_segment_id))
            
            self.results_list.addItem(item)
            self.results_list.setItemWidget(item, card)

    def _handle_query_failed(self, error: str) -> None:
        self.search_button.setEnabled(True)
        LOGGER.error("Search failed: %s", error)

    def _handle_item_double_clicked(self, item: QListWidgetItem) -> None:
        session_id, segment_id = item.data(Qt.ItemDataRole.UserRole)
        if session_id:
            self.source_navigation_requested.emit(str(session_id), str(segment_id or ""))
