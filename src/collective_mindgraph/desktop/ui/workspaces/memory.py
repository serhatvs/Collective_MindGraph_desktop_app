"""Unified meeting-memory search and answer workspace."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ...contracts import MemoryAnswer, MemorySearchItem
from ...engine_client import EngineClient, EngineClientError
from ...language_catalog import LanguageCatalog
from ..job_presenter import JobPresenter
from ..state_panel import StatePanel


class MemoryWorkspace(QWidget):
    def __init__(
        self,
        client: EngineClient,
        catalog: LanguageCatalog,
        presenter: JobPresenter,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._catalog = catalog
        self._presenter = presenter
        self._search_items: tuple[MemorySearchItem, ...] = ()
        self._memory_answer: MemoryAnswer | None = None
        self._search_cursor: str | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        self._title = QLabel()
        self._title.setObjectName("WorkspaceTitle")
        layout.addWidget(self._title)
        controls = QHBoxLayout()
        self._query = QLineEdit()
        self._query.returnPressed.connect(self.run)
        self._mode = QComboBox()
        self._search = QPushButton()
        self._search.clicked.connect(lambda: self.run(ask=False))
        self._ask = QPushButton()
        self._ask.setObjectName("Primary")
        self._ask.clicked.connect(lambda: self.run(ask=True))
        controls.addWidget(self._query, 1)
        controls.addWidget(self._mode)
        controls.addWidget(self._search)
        controls.addWidget(self._ask)
        layout.addLayout(controls)

        self._tabs = QTabWidget()
        self._answer = QTextBrowser()
        self._tabs.addTab(self._answer, "")
        self._results = QTableWidget(0, 5)
        self._tabs.addTab(self._results, "")
        self._sources = QTextBrowser()
        self._tabs.addTab(self._sources, "")
        self._reasoning = QTextBrowser()
        self._tabs.addTab(self._reasoning, "")
        layout.addWidget(self._tabs, 1)
        self._load_more = QPushButton()
        self._load_more.clicked.connect(self._load_more_results)
        self._load_more.setVisible(False)
        layout.addWidget(self._load_more)
        self.state_panel = StatePanel(catalog)
        self.state_panel.retry_requested.connect(self.run)
        layout.addWidget(self.state_panel)
        catalog.language_changed.connect(self.retranslate)
        self.retranslate()

    def set_query_and_ask(self, query: str) -> None:
        self._query.setText(query)
        self.run(ask=True)

    def run(self, ask: bool = False) -> None:
        query = self._query.text().strip()
        if not query:
            return
        mode = str(self._mode.currentData() or "hybrid")
        self.state_panel.show_state("loading")
        if ask:

            def operation():
                return self._client.ask_memory(query, mode="evidence_only")

            succeeded = self._answer_loaded
        else:

            def operation():
                return self._client.search_memory(query, mode=mode)

            def succeeded(value: object) -> None:
                self._search_loaded(value, append=False)

        self._presenter.submit(
            operation,
            succeeded=succeeded,
            failed=self._failed,
        )

    def _search_loaded(self, value: object, *, append: bool) -> None:
        items, self._search_cursor = value
        self._search_items = (*self._search_items, *items) if append else tuple(items)
        self.state_panel.clear()
        self._render_search_items()
        self._tabs.setCurrentIndex(1)
        self._load_more.setVisible(self._search_cursor is not None)
        if not self._search_items:
            self.state_panel.show_state("empty")

    def _load_more_results(self) -> None:
        query = self._query.text().strip()
        if not query or self._search_cursor is None:
            return
        mode = str(self._mode.currentData() or "hybrid")
        self._presenter.submit(
            lambda: self._client.search_memory(
                query,
                mode=mode,
                cursor=self._search_cursor,
            ),
            succeeded=lambda value: self._search_loaded(value, append=True),
            failed=self._failed,
        )

    def _render_search_items(self) -> None:
        items = self._search_items
        self._results.setRowCount(len(items))
        for row, item in enumerate(items):
            assert isinstance(item, MemorySearchItem)
            values = (
                _localized_kind(self._catalog, item.kind),
                item.text,
                f"{item.score:.2f}",
                item.meeting_id,
                item.evidence_id or "—",
            )
            for column, text in enumerate(values):
                self._results.setItem(row, column, QTableWidgetItem(text))
        self._results.resizeColumnsToContents()

    def _answer_loaded(self, value: object) -> None:
        assert isinstance(value, MemoryAnswer)
        self._memory_answer = value
        self.state_panel.clear()
        self._answer.setPlainText(value.answer)
        self._render_answer_sources()
        reasoning_lines = [str(chain.get("explanation") or "") for chain in value.evidence_chains]
        self._reasoning.setPlainText(
            "\n\n".join(reasoning_lines) or self._catalog.text("common.empty")
        )
        self._tabs.setCurrentIndex(0)

    def _render_answer_sources(self) -> None:
        if self._memory_answer is None:
            return
        value = self._memory_answer
        self._sources.setPlainText(
            "\n".join(
                (
                    *(
                        self._catalog.text("memory.meeting_source", id=item)
                        for item in value.source_meeting_ids
                    ),
                    *(
                        self._catalog.text("memory.segment_source", id=item)
                        for item in value.source_segment_ids
                    ),
                )
            )
            or self._catalog.text("common.empty")
        )

    def _failed(self, error: Exception) -> None:
        self.state_panel.show_state(
            "offline" if isinstance(error, EngineClientError) else "error",
            str(error),
        )

    def retranslate(self) -> None:
        tr = self._catalog.text
        self._title.setText(tr("memory.title"))
        self._query.setPlaceholderText(tr("memory.placeholder"))
        self._search.setText(tr("common.search"))
        self._ask.setText(tr("memory.ask"))
        self._load_more.setText(tr("common.load_more"))
        self._results.setHorizontalHeaderLabels(
            [
                tr("common.type"),
                tr("common.result"),
                tr("common.score"),
                tr("common.meeting"),
                tr("common.source"),
            ]
        )
        current = self._mode.currentData()
        self._mode.clear()
        for key, mode in (
            ("memory.mode.hybrid", "hybrid"),
            ("memory.mode.keyword", "keyword"),
            ("memory.mode.semantic", "semantic"),
        ):
            self._mode.addItem(tr(key), mode)
        if current:
            self._mode.setCurrentIndex(max(0, self._mode.findData(current)))
        for index, key in enumerate(
            ("memory.answer", "common.search", "memory.sources", "memory.reasoning")
        ):
            self._tabs.setTabText(index, tr(key))
        self._render_search_items()
        self._render_answer_sources()


def _localized_kind(catalog: LanguageCatalog, kind: str) -> str:
    key = f"insight.{kind}"
    translated = catalog.text(key)
    return kind if translated == key else translated
