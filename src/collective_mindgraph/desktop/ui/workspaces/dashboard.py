"""Home dashboard workspace."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...contracts import DashboardSnapshot, EngineHealth
from ...language_catalog import LanguageCatalog
from ..state_panel import StatePanel


class DashboardWorkspace(QWidget):
    capture_requested = Signal()
    file_requested = Signal()
    ask_requested = Signal(str)
    meeting_requested = Signal(int)
    refresh_requested = Signal()

    def __init__(self, catalog: LanguageCatalog, parent=None) -> None:
        super().__init__(parent)
        self._catalog = catalog
        self._snapshot: DashboardSnapshot | None = None
        self._health: EngineHealth | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)
        self._title = QLabel()
        self._title.setObjectName("HeroTitle")
        self._subtitle = QLabel()
        self._subtitle.setObjectName("Muted")
        self._subtitle.setWordWrap(True)
        layout.addWidget(self._title)
        layout.addWidget(self._subtitle)

        quick = QHBoxLayout()
        self._capture = QPushButton()
        self._capture.setObjectName("Primary")
        self._capture.clicked.connect(self.capture_requested)
        self._file = QPushButton()
        self._file.clicked.connect(self.file_requested)
        quick.addWidget(self._capture)
        quick.addWidget(self._file)
        quick.addStretch()
        layout.addLayout(quick)

        metrics = QGridLayout()
        self._meeting_count = _metric_card(metrics, 0, 0)
        self._review_count = _metric_card(metrics, 0, 1)
        self._knowledge_count = _metric_card(metrics, 0, 2)
        self._engine_state = _metric_card(metrics, 0, 3)
        layout.addLayout(metrics)

        lower = QHBoxLayout()
        recent_card = _card()
        recent_layout = QVBoxLayout(recent_card)
        self._recent_title = QLabel()
        self._recent_title.setStyleSheet("font-weight: 700")
        self._recent_items = QVBoxLayout()
        recent_layout.addWidget(self._recent_title)
        recent_layout.addLayout(self._recent_items)
        recent_layout.addStretch()
        lower.addWidget(recent_card, 2)

        ask_card = _card()
        ask_layout = QVBoxLayout(ask_card)
        self._ask_title = QLabel()
        self._ask_title.setStyleSheet("font-weight: 700")
        self._question = QLineEdit()
        self._ask = QPushButton()
        self._ask.setObjectName("Primary")
        self._ask.clicked.connect(lambda: self.ask_requested.emit(self._question.text().strip()))
        ask_layout.addWidget(self._ask_title)
        ask_layout.addWidget(self._question)
        ask_layout.addWidget(self._ask)
        ask_layout.addStretch()
        lower.addWidget(ask_card, 1)
        layout.addLayout(lower, 1)
        self.state_panel = StatePanel(catalog)
        self.state_panel.retry_requested.connect(self.refresh_requested)
        layout.addWidget(self.state_panel)
        catalog.language_changed.connect(self.retranslate)
        self.retranslate()

    def update_snapshot(
        self,
        snapshot: DashboardSnapshot,
        health: EngineHealth,
    ) -> None:
        self._snapshot = snapshot
        self._health = health
        self.state_panel.clear()
        self._meeting_count.value.setText(str(snapshot.total_meetings))
        self._review_count.value.setText(str(snapshot.pending_reviews))
        self._knowledge_count.value.setText(str(snapshot.total_knowledge_nodes))
        self._engine_state.value.setText(self._catalog.text(f"status.{health.status}"))
        _clear_layout(self._recent_items)
        for meeting in snapshot.recent_meetings:
            button = QPushButton(meeting.title)
            button.clicked.connect(
                lambda _checked=False, item_id=meeting.id: self.meeting_requested.emit(item_id)
            )
            self._recent_items.addWidget(button)
        if not snapshot.recent_meetings:
            empty = QLabel(self._catalog.text("common.empty"))
            empty.setObjectName("Muted")
            self._recent_items.addWidget(empty)

    def show_error(self, detail: str, *, offline: bool = False) -> None:
        self.state_panel.show_state("offline" if offline else "error", detail)

    def retranslate(self) -> None:
        tr = self._catalog.text
        self._title.setText(tr("dashboard.welcome"))
        self._subtitle.setText(tr("dashboard.subtitle"))
        self._capture.setText(tr("dashboard.quick_capture"))
        self._file.setText(tr("dashboard.add_file"))
        self._recent_title.setText(tr("dashboard.recent"))
        self._ask_title.setText(tr("dashboard.ask"))
        self._question.setPlaceholderText(tr("memory.placeholder"))
        self._ask.setText(tr("memory.ask"))
        labels = (
            (self._meeting_count, tr("nav.meetings")),
            (self._review_count, tr("dashboard.pending")),
            (self._knowledge_count, tr("nav.knowledge")),
            (self._engine_state, tr("dashboard.engine")),
        )
        for card, label in labels:
            card.label.setText(label)
        if self._snapshot is not None and self._health is not None:
            self.update_snapshot(self._snapshot, self._health)


def _card() -> QFrame:
    frame = QFrame()
    frame.setObjectName("Card")
    return frame


class MetricCard(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Card")
        card_layout = QVBoxLayout(self)
        self.value = QLabel("—")
        self.value.setStyleSheet("font-size: 24px; font-weight: 750")
        self.label = QLabel()
        self.label.setObjectName("Muted")
        card_layout.addWidget(self.value)
        card_layout.addWidget(self.label)


def _metric_card(layout: QGridLayout, row: int, column: int) -> MetricCard:
    card = MetricCard()
    layout.addWidget(card, row, column)
    return card


def _clear_layout(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
