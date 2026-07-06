"""Global Memory Search page with categorized results and reasoning traces."""

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
    QComboBox,
)

from ...transcription import (
    QueryResultItem,
    QueryResponse,
    ReasoningResponse,
    RealtimeBackendTranscriptionConfig,
    RealtimeBackendTranscriptionService,
)
from ..components.ask_memory_panel import AskMemoryPanel
from ..components.result_card import ResultCard
from ..widgets import CardWidget, EmptyStateWidget

LOGGER = logging.getLogger(__name__)

class MemoryQueryWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    reasoning_finished = Signal(object)

    def __init__(
        self,
        query: str,
        mode: str,
        config: RealtimeBackendTranscriptionConfig,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._query = query
        self._mode = mode
        self._config = config

    @Slot()
    def run(self) -> None:
        try:
            service = RealtimeBackendTranscriptionService(config=self._config)
            # Regular Query
            result = service.query_memory(self._query, mode=self._mode)
            self.finished.emit(result)
            
            # Optional Reasoning
            try:
                reason_resp = service.reason_memory(self._query)
                self.reasoning_finished.emit(reason_resp)
            except Exception:
                pass 
        except Exception as exc:
            self.failed.emit(str(exc))
            return


class MemorySearchPage(QWidget):
    source_navigation_requested = Signal(str, str) # session_id, segment_id
    reasoning_trace_available = Signal(object) # ReasoningResponse

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config: RealtimeBackendTranscriptionConfig | None = None
        self._query_thread: QThread | None = None
        self._query_worker: MemoryQueryWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        self.card = CardWidget("Search Memory")
        layout.addWidget(self.card, 1)

        # Ask Memory Section
        self.ask_panel = AskMemoryPanel()
        self.ask_panel.source_navigation_requested.connect(self.source_navigation_requested)
        layout.insertWidget(0, self.ask_panel)

        search_container = QWidget()
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search technical memory, tasks, or decisions...")
        self.search_input.setMinimumHeight(44)
        self.search_input.setStyleSheet("font-size: 11pt; padding-left: 12px;")
        self.search_input.returnPressed.connect(self._handle_search)
        
        self.mode_selector = QComboBox()
        self.mode_selector.addItems(["Hybrid", "Semantic", "Keyword"])
        self.mode_selector.setMinimumHeight(44)
        self.mode_selector.setMinimumWidth(120)
        
        self.search_button = QPushButton("Query Memory")
        self.search_button.setMinimumHeight(44)
        self.search_button.setMinimumWidth(140)
        self.search_button.clicked.connect(self._handle_search)
        
        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(self.mode_selector)
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
            "Global Memory Query",
            "Enter keywords (e.g. 'FastAPI', 'endpoint') to find linked context from across your session memory history."
        )
        self.card.body_layout.addWidget(self.empty_state)
        self.results_list.hide()

    def set_config(self, config: RealtimeBackendTranscriptionConfig) -> None:
        self._config = config
        self.ask_panel.set_config(config)

    def _handle_search(self) -> None:
        query = self.search_input.text().strip()
        mode = self.mode_selector.currentText().lower()
        if not query:
            self.empty_state.set_text("Search Memory", "Enter a query to search sessions, tasks, decisions, and graph context.")
            self.empty_state.show()
            self.results_list.hide()
            return
        if not self._config:
            self.empty_state.set_text("Search Unavailable", "Open Global Search from the sidebar so the page can use the current backend settings.")
            self.empty_state.show()
            self.results_list.hide()
            return
        if self._query_thread is not None:
            return

        self.search_button.setEnabled(False)
        self.results_list.clear()
        self.empty_state.set_text("Searching Memory", "Querying the local backend...")
        self.empty_state.show()
        self.results_list.hide()

        self._query_thread = QThread()
        self._query_worker = MemoryQueryWorker(query, mode, self._config)
        self._query_worker.moveToThread(self._query_thread)
        
        self._query_thread.started.connect(self._query_worker.run)
        self._query_worker.finished.connect(self._handle_query_finished)
        self._query_worker.failed.connect(self._handle_query_failed)
        self._query_worker.reasoning_finished.connect(self._handle_reasoning_finished)
        self._query_worker.finished.connect(self._query_thread.quit)
        self._query_worker.failed.connect(self._query_thread.quit)
        self._query_thread.finished.connect(self._cleanup_query_worker)
        
        self._query_thread.start()

    def _handle_query_finished(self, response: QueryResponse) -> None:
        self.search_button.setEnabled(True)
        
        if response.warnings:
            # We could show warnings in UI, for now log
            for w in response.warnings:
                LOGGER.warning("Query Warning: %s", w)

        if not response.results:
            self.empty_state.set_text("No Matches Found", "Try a different term, or ingest/review memory first.")
            self.empty_state.show()
            self.results_list.hide()
            return

        self.empty_state.hide()
        self.results_list.show()

        for res in response.results:
            card = ResultCard()
            matched = res.matched_by or "unknown"
            meta = f"Memory: {res.source_session_id} | Relevance: {res.score:.2f} [{matched}]"
            
            preview = res.preview or ""
            if res.edge_path:
                preview = f"Path: {res.edge_path}\n{preview}"
                
            card.set_result(res.result_type, res.text, preview, meta, res.matched_terms)
            
            item = QListWidgetItem(self.results_list)
            item.setSizeHint(card.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, (res.source_session_id, res.source_segment_id))
            
            self.results_list.addItem(item)
            self.results_list.setItemWidget(item, card)

    @Slot(object)
    def _handle_reasoning_finished(self, response: ReasoningResponse) -> None:
        if response.chains:
            self.reasoning_trace_available.emit(response)

    def _handle_query_failed(self, error: str) -> None:
        self.search_button.setEnabled(True)
        self.empty_state.set_text("Search Failed", error)
        self.empty_state.show()
        self.results_list.hide()
        LOGGER.error("Search failed: %s", error)

    def _cleanup_query_worker(self) -> None:
        self._query_thread = None
        self._query_worker = None

    def _handle_item_double_clicked(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if data and len(data) == 2:
            session_id, segment_id = data
            if session_id:
                self.source_navigation_requested.emit(str(session_id), str(segment_id or ""))
