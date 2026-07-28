"""Review and advanced knowledge-table workspace."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ...contracts import InsightItem, KnowledgeItem, KnowledgeRelationship
from ...engine_client import EngineClient, EngineClientError
from ...language_catalog import LanguageCatalog
from ..job_presenter import JobPresenter
from ..state_panel import StatePanel


class KnowledgeWorkspace(QWidget):
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
        self._insights: tuple[InsightItem, ...] = ()
        self._nodes: tuple[KnowledgeItem, ...] = ()
        self._edges: tuple[KnowledgeRelationship, ...] = ()
        self._insight_cursor: str | None = None
        self._node_cursor: str | None = None
        self._edge_cursor: str | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        self._title = QLabel()
        self._title.setObjectName("WorkspaceTitle")
        layout.addWidget(self._title)
        filters = QHBoxLayout()
        self._query = QLineEdit()
        self._query.returnPressed.connect(self.refresh)
        self._kind = QComboBox()
        self._review = QComboBox()
        self._refresh = QPushButton()
        self._refresh.clicked.connect(self.refresh)
        filters.addWidget(self._query, 1)
        filters.addWidget(self._kind)
        filters.addWidget(self._review)
        filters.addWidget(self._refresh)
        layout.addLayout(filters)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._tabs = QTabWidget()
        self._review_table = QTableWidget(0, 5)
        self._tabs.addTab(self._review_table, "")
        self._node_table = QTableWidget(0, 4)
        self._node_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._node_table.itemSelectionChanged.connect(self._show_selected)
        self._tabs.addTab(self._node_table, "")
        self._edge_table = QTableWidget(0, 4)
        self._tabs.addTab(self._edge_table, "")
        splitter.addWidget(self._tabs)
        self._detail = QTextBrowser()
        splitter.addWidget(self._detail)
        splitter.setSizes([760, 320])
        layout.addWidget(splitter, 1)
        self._load_more = QPushButton()
        self._load_more.clicked.connect(self._load_more_page)
        self._tabs.currentChanged.connect(self._update_more_button)
        layout.addWidget(self._load_more)
        self.state_panel = StatePanel(catalog)
        self.state_panel.retry_requested.connect(self.refresh)
        layout.addWidget(self.state_panel)
        catalog.language_changed.connect(self.retranslate)
        self.retranslate()

    def refresh(self) -> None:
        query = self._query.text().strip()
        kind = self._kind.currentData()
        review = self._review.currentData()
        self.state_panel.show_state("loading")

        def operation():
            return (
                self._client.list_insights(review="pending", query=query),
                self._client.list_knowledge(
                    query=query,
                    kind=str(kind) if kind else None,
                    review=str(review) if review else None,
                ),
                self._client.list_relationships(query=query),
            )

        self._presenter.submit(
            operation,
            succeeded=self._loaded,
            failed=self._failed,
        )

    def _loaded(self, value: object) -> None:
        insight_page, node_page, edge_page = value
        insights, self._insight_cursor = insight_page
        nodes, self._node_cursor = node_page
        edges, self._edge_cursor = edge_page
        self._insights = tuple(insights)
        self._nodes = tuple(nodes)
        self._edges = tuple(edges)
        self.state_panel.clear()
        self._render_reviews()
        self._render_nodes()
        self._render_edges()
        if not self._insights and not self._nodes:
            self.state_panel.show_state("empty")
        self._update_more_button()

    def _load_more_page(self) -> None:
        query = self._query.text().strip()
        kind = self._kind.currentData()
        review = self._review.currentData()
        index = self._tabs.currentIndex()
        if index == 0 and self._insight_cursor:

            def operation():
                return (
                    "insights",
                    self._client.list_insights(
                        review="pending",
                        query=query,
                        cursor=self._insight_cursor,
                    ),
                )

        elif index == 1 and self._node_cursor:

            def operation():
                return (
                    "nodes",
                    self._client.list_knowledge(
                        query=query,
                        kind=str(kind) if kind else None,
                        review=str(review) if review else None,
                        cursor=self._node_cursor,
                    ),
                )

        elif index == 2 and self._edge_cursor:

            def operation():
                return (
                    "edges",
                    self._client.list_relationships(
                        query=query,
                        cursor=self._edge_cursor,
                    ),
                )

        else:
            return
        self._presenter.submit(
            operation,
            succeeded=self._page_loaded,
            failed=self._failed,
        )

    def _page_loaded(self, value: object) -> None:
        kind, page = value
        items, cursor = page
        if kind == "insights":
            self._insights = (*self._insights, *items)
            self._insight_cursor = cursor
            self._render_reviews()
        elif kind == "nodes":
            self._nodes = (*self._nodes, *items)
            self._node_cursor = cursor
            self._render_nodes()
        else:
            self._edges = (*self._edges, *items)
            self._edge_cursor = cursor
            self._render_edges()
        self._update_more_button()

    def _update_more_button(self, _index: int | None = None) -> None:
        cursors = (
            self._insight_cursor,
            self._node_cursor,
            self._edge_cursor,
        )
        self._load_more.setVisible(cursors[self._tabs.currentIndex()] is not None)

    def _render_reviews(self) -> None:
        self._review_table.setRowCount(len(self._insights))
        for row, insight in enumerate(self._insights):
            self._review_table.setItem(
                row,
                0,
                QTableWidgetItem(_localized(self._catalog, "insight", insight.kind)),
            )
            self._review_table.setItem(row, 1, QTableWidgetItem(insight.title))
            self._review_table.setItem(row, 2, QTableWidgetItem(insight.body))
            self._review_table.setItem(
                row,
                3,
                QTableWidgetItem(_localized(self._catalog, "status", insight.review)),
            )
            actions = QWidget()
            action_layout = QHBoxLayout(actions)
            action_layout.setContentsMargins(0, 0, 0, 0)
            accept = QPushButton(self._catalog.text("common.accept"))
            reject = QPushButton(self._catalog.text("common.reject"))
            accept.clicked.connect(
                lambda _checked=False, item_id=insight.id, item_row=row: self._review_item(
                    item_id, "accepted", item_row
                )
            )
            reject.clicked.connect(
                lambda _checked=False, item_id=insight.id, item_row=row: self._review_item(
                    item_id, "rejected", item_row
                )
            )
            action_layout.addWidget(accept)
            action_layout.addWidget(reject)
            self._review_table.setCellWidget(row, 4, actions)

    def _render_nodes(self) -> None:
        selected_item = self._node_table.item(self._node_table.currentRow(), 0)
        selected_id = (
            str(selected_item.data(Qt.ItemDataRole.UserRole)) if selected_item is not None else None
        )
        self._node_table.setRowCount(len(self._nodes))
        for row, node in enumerate(self._nodes):
            first = QTableWidgetItem(_localized(self._catalog, "insight", node.kind))
            first.setData(Qt.ItemDataRole.UserRole, node.id)
            self._node_table.setItem(row, 0, first)
            self._node_table.setItem(row, 1, QTableWidgetItem(node.title))
            self._node_table.setItem(
                row,
                2,
                QTableWidgetItem(str(node.meeting_id or "—")),
            )
            self._node_table.setItem(
                row,
                3,
                QTableWidgetItem(
                    _localized(
                        self._catalog,
                        "status",
                        str(node.attributes.get("review", "accepted")),
                    )
                ),
            )
        self._node_table.resizeColumnsToContents()
        if selected_id is not None:
            for row, node in enumerate(self._nodes):
                if node.id == selected_id:
                    self._node_table.selectRow(row)
                    break

    def _render_edges(self) -> None:
        self._edge_table.setRowCount(len(self._edges))
        for row, edge in enumerate(self._edges):
            values = (
                edge.kind,
                edge.source_id,
                edge.target_id,
                edge.evidence_id or "—",
            )
            for column, text in enumerate(values):
                self._edge_table.setItem(row, column, QTableWidgetItem(text))
        self._edge_table.resizeColumnsToContents()

    def _show_selected(self) -> None:
        row = self._node_table.currentRow()
        item = self._node_table.item(row, 0) if row >= 0 else None
        if item is None:
            return
        node_id = str(item.data(Qt.ItemDataRole.UserRole))
        node = next((item for item in self._nodes if item.id == node_id), None)
        if node is None:
            return
        edges = [edge for edge in self._edges if node.id in {edge.source_id, edge.target_id}]
        relation_text = "\n".join(
            f"{edge.kind}: {edge.source_id} → {edge.target_id}" for edge in edges
        )
        self._detail.setPlainText(
            f"{node.title}\n\n{node.body}\n\n"
            f"{self._catalog.text('common.evidence')}: "
            f"{node.evidence_id or '—'}\n\n{relation_text}"
        )

    def _review_item(self, insight_id: str, decision: str, row: int) -> None:
        original = next(item for item in self._insights if item.id == insight_id)
        title_item = self._review_table.item(row, 1)
        body_item = self._review_table.item(row, 2)
        title = title_item.text().strip() if title_item is not None else original.title
        body = body_item.text().strip() if body_item is not None else original.body
        self._presenter.submit(
            lambda: self._client.review_insight(
                insight_id,
                decision,
                title=title if title != original.title else None,
                body=body if body != original.body else None,
            ),
            succeeded=lambda _value: self.refresh(),
            failed=self._failed,
        )

    def _failed(self, error: Exception) -> None:
        self.state_panel.show_state(
            "offline" if isinstance(error, EngineClientError) else "error",
            str(error),
        )

    def retranslate(self) -> None:
        tr = self._catalog.text
        self._title.setText(tr("knowledge.title"))
        self._query.setPlaceholderText(tr("common.search"))
        self._refresh.setText(tr("common.refresh"))
        self._load_more.setText(tr("common.load_more"))
        self._review_table.setHorizontalHeaderLabels(
            [
                tr("common.type"),
                tr("common.title"),
                tr("common.detail"),
                tr("common.review"),
                tr("common.actions"),
            ]
        )
        self._node_table.setHorizontalHeaderLabels(
            [
                tr("common.type"),
                tr("common.title"),
                tr("common.meeting"),
                tr("common.review"),
            ]
        )
        self._edge_table.setHorizontalHeaderLabels(
            [
                tr("common.relationship"),
                tr("common.source"),
                tr("common.target"),
                tr("common.evidence"),
            ]
        )
        current_kind = self._kind.currentData()
        self._kind.clear()
        self._kind.addItem(tr("knowledge.filter.kind"), None)
        for kind in ("task", "decision", "topic", "person", "risk", "entity"):
            self._kind.addItem(_localized(self._catalog, "insight", kind), kind)
        if current_kind:
            self._kind.setCurrentIndex(max(0, self._kind.findData(current_kind)))
        current_review = self._review.currentData()
        self._review.clear()
        self._review.addItem(tr("knowledge.filter.review"), None)
        for review in ("pending", "accepted", "rejected"):
            self._review.addItem(tr(f"status.{review}"), review)
        if current_review:
            self._review.setCurrentIndex(max(0, self._review.findData(current_review)))
        for index, key in enumerate(("knowledge.review", "knowledge.nodes", "knowledge.edges")):
            self._tabs.setTabText(index, tr(key))
        self._render_reviews()
        self._render_nodes()
        self._render_edges()


def _localized(catalog: LanguageCatalog, group: str, value: str) -> str:
    key = f"{group}.{value}"
    translated = catalog.text(key)
    return value if translated == key else translated
