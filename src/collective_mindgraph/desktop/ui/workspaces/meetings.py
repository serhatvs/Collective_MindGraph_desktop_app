"""Meeting library and source-preserving detail workspace."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...contracts import EvidenceItem, InsightItem, MeetingSummary, MeetingTranscript
from ...engine_client import EngineClient, EngineClientError, is_engine_offline_error
from ...language_catalog import LanguageCatalog
from ..job_presenter import JobPresenter
from ..state_panel import StatePanel


class MeetingsWorkspace(QWidget):
    refresh_requested = Signal()

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
        self._meetings: list[MeetingSummary] = []
        self._selected_meeting: MeetingSummary | None = None
        self._transcript: MeetingTranscript | None = None
        self._insights: tuple[InsightItem, ...] = ()
        self._evidence_items: tuple[EvidenceItem, ...] = ()
        self._meeting_cursor: str | None = None
        self._insight_cursor: str | None = None
        self._evidence_cursor: str | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        self._title = QLabel()
        self._title.setObjectName("WorkspaceTitle")
        layout.addWidget(self._title)
        self._filter = QLineEdit()
        self._filter.returnPressed.connect(self.refresh)
        self._filter.textChanged.connect(self._filter_local)
        layout.addWidget(self._filter)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._meeting_table = QTableWidget(0, 2)
        self._meeting_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._meeting_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._meeting_table.itemSelectionChanged.connect(self._meeting_selected)
        splitter.addWidget(self._meeting_table)

        self._tabs = QTabWidget()
        self._overview = QLabel()
        self._overview.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._overview.setWordWrap(True)
        self._tabs.addTab(self._overview, "")

        transcript_tab = QWidget()
        transcript_layout = QVBoxLayout(transcript_tab)
        self._segment_table = QTableWidget(0, 4)
        self._segment_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        transcript_layout.addWidget(self._segment_table)
        correction = QHBoxLayout()
        self._correction = QLineEdit()
        self._save_correction = QPushButton()
        self._save_correction.clicked.connect(self._save_selected_correction)
        correction.addWidget(self._correction, 1)
        correction.addWidget(self._save_correction)
        transcript_layout.addLayout(correction)
        self._tabs.addTab(transcript_tab, "")

        self._insight_table = QTableWidget(0, 4)
        self._tabs.addTab(self._insight_table, "")
        self._evidence = QLabel()
        self._evidence.setWordWrap(True)
        self._evidence.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._tabs.addTab(self._evidence, "")
        splitter.addWidget(self._tabs)
        splitter.setSizes([320, 760])
        layout.addWidget(splitter, 1)
        more_actions = QHBoxLayout()
        self._meeting_more = QPushButton()
        self._meeting_more.clicked.connect(self._load_more_meetings)
        self._detail_more = QPushButton()
        self._detail_more.clicked.connect(self._load_more_detail)
        self._tabs.currentChanged.connect(self._update_detail_more)
        more_actions.addWidget(self._meeting_more)
        more_actions.addStretch(1)
        more_actions.addWidget(self._detail_more)
        layout.addLayout(more_actions)
        self.state_panel = StatePanel(catalog)
        self.state_panel.retry_requested.connect(self.refresh)
        layout.addWidget(self.state_panel)
        catalog.language_changed.connect(self.retranslate)
        self.retranslate()

    def refresh(self, select_id: int | None = None) -> None:
        self.state_panel.show_state("loading")
        self._presenter.submit(
            lambda: self._client.list_meetings(self._filter.text().strip()),
            succeeded=lambda value: self._meetings_loaded(value, select_id, False),
            failed=self._failed,
        )

    def select_meeting(self, meeting_id: int) -> None:
        for row, meeting in enumerate(self._meetings):
            if meeting.id == meeting_id:
                self._meeting_table.selectRow(row)
                return
        self.refresh(select_id=meeting_id)

    def _meetings_loaded(
        self,
        value: object,
        select_id: int | None,
        append: bool,
    ) -> None:
        meetings, cursor = value
        self._meeting_cursor = cursor
        if append:
            self._meetings.extend(meetings)
        else:
            self._meetings = list(meetings)
        self._render_meetings(self._meetings)
        self._meeting_more.setVisible(self._meeting_cursor is not None)
        self._meeting_more.setEnabled(True)
        self.state_panel.clear()
        if not self._meetings:
            self.state_panel.show_state("empty")
        if select_id is not None:
            self.select_meeting(select_id)

    def _load_more_meetings(self) -> None:
        if self._meeting_cursor is None:
            return
        self._meeting_more.setEnabled(False)
        self._presenter.submit(
            lambda: self._client.list_meetings(
                self._filter.text().strip(),
                cursor=self._meeting_cursor,
            ),
            succeeded=lambda value: self._meetings_loaded(value, None, True),
            failed=self._failed,
        )

    def _render_meetings(self, meetings: list[MeetingSummary]) -> None:
        self._meeting_table.setRowCount(len(meetings))
        for row, meeting in enumerate(meetings):
            title = QTableWidgetItem(meeting.title)
            title.setData(Qt.ItemDataRole.UserRole, meeting.id)
            self._meeting_table.setItem(row, 0, title)
            self._meeting_table.setItem(
                row,
                1,
                QTableWidgetItem(_localized(self._catalog, "status", meeting.status)),
            )
        self._meeting_table.resizeColumnsToContents()

    def _filter_local(self, query: str) -> None:
        normalized = query.casefold().strip()
        visible = [
            meeting
            for meeting in self._meetings
            if not normalized or normalized in meeting.title.casefold()
        ]
        self._render_meetings(visible)

    def _meeting_selected(self) -> None:
        row = self._meeting_table.currentRow()
        item = self._meeting_table.item(row, 0) if row >= 0 else None
        if item is None:
            return
        meeting_id = int(item.data(Qt.ItemDataRole.UserRole))
        meeting = next((item for item in self._meetings if item.id == meeting_id), None)
        if meeting is None:
            return
        self._selected_meeting = meeting
        self._render_overview()

        def operation():
            try:
                transcript = self._client.get_transcript(meeting_id)
            except EngineClientError as error:
                if error.status_code != 404:
                    raise
                transcript = None
            insights = self._client.list_insights(meeting_id=meeting_id)
            evidence = self._client.list_evidence(meeting_id)
            return transcript, insights, evidence

        self._presenter.submit(
            operation,
            succeeded=self._detail_loaded,
            failed=self._failed,
        )

    def _detail_loaded(self, value: object) -> None:
        transcript, insight_page, evidence_page = value
        insights, self._insight_cursor = insight_page
        evidence, self._evidence_cursor = evidence_page
        self._transcript = transcript
        self._insights = insights
        self._evidence_items = evidence
        self._render_transcript()
        self._render_insights()
        self._update_detail_more()

    def _load_more_detail(self) -> None:
        if self._selected_meeting is None:
            return
        meeting_id = self._selected_meeting.id
        if self._tabs.currentIndex() == 2 and self._insight_cursor:

            def operation():
                return (
                    "insights",
                    self._client.list_insights(
                        meeting_id=meeting_id,
                        cursor=self._insight_cursor,
                    ),
                )

        elif self._tabs.currentIndex() == 3 and self._evidence_cursor:

            def operation():
                return (
                    "evidence",
                    self._client.list_evidence(
                        meeting_id,
                        cursor=self._evidence_cursor,
                    ),
                )

        else:
            return
        self._presenter.submit(
            operation,
            succeeded=self._detail_page_loaded,
            failed=self._failed,
        )

    def _detail_page_loaded(self, value: object) -> None:
        kind, page = value
        items, cursor = page
        if kind == "insights":
            self._insights = (*self._insights, *items)
            self._insight_cursor = cursor
        else:
            self._evidence_items = (*self._evidence_items, *items)
            self._evidence_cursor = cursor
        self._render_insights()
        self._detail_more.setEnabled(True)
        self._update_detail_more()

    def _update_detail_more(self, _index: int | None = None) -> None:
        visible = (self._tabs.currentIndex() == 2 and self._insight_cursor is not None) or (
            self._tabs.currentIndex() == 3 and self._evidence_cursor is not None
        )
        self._detail_more.setVisible(visible)

    def _render_transcript(self) -> None:
        segments = self._transcript.segments if self._transcript else ()
        self._segment_table.setRowCount(len(segments))
        for row, segment in enumerate(segments):
            speaker = QTableWidgetItem(segment.speaker_label or "—")
            speaker.setData(Qt.ItemDataRole.UserRole, segment.id)
            self._segment_table.setItem(row, 0, speaker)
            self._segment_table.setItem(
                row,
                1,
                QTableWidgetItem(f"{segment.start_seconds:.1f}–{segment.end_seconds:.1f}"),
            )
            self._segment_table.setItem(row, 2, QTableWidgetItem(segment.raw_text))
            self._segment_table.setItem(
                row,
                3,
                QTableWidgetItem(segment.corrected_text),
            )
        self._segment_table.resizeColumnsToContents()

    def _render_insights(self) -> None:
        self._insight_table.setRowCount(len(self._insights))
        for row, insight in enumerate(self._insights):
            self._insight_table.setItem(
                row,
                0,
                QTableWidgetItem(_localized(self._catalog, "insight", insight.kind)),
            )
            self._insight_table.setItem(row, 1, QTableWidgetItem(insight.title))
            self._insight_table.setItem(
                row,
                2,
                QTableWidgetItem(_localized(self._catalog, "status", insight.review)),
            )
            self._insight_table.setItem(
                row,
                3,
                QTableWidgetItem(insight.evidence_id or "—"),
            )
        evidence_lines = [
            (
                f"{item.start_seconds:.1f}–{item.end_seconds:.1f}s\n"
                f"{item.text_preview or self._catalog.text('common.empty')}"
            )
            if item.start_seconds is not None and item.end_seconds is not None
            else (item.text_preview or self._catalog.text("common.empty"))
            for item in self._evidence_items
        ]
        self._evidence.setText("\n\n".join(evidence_lines) or self._catalog.text("common.empty"))

    def _save_selected_correction(self) -> None:
        row = self._segment_table.currentRow()
        item = self._segment_table.item(row, 0) if row >= 0 else None
        corrected = self._correction.text().strip()
        if item is None or not corrected:
            return
        segment_id = str(item.data(Qt.ItemDataRole.UserRole))
        self._presenter.submit(
            lambda: self._client.update_segment(segment_id, corrected),
            succeeded=lambda _value: self._after_correction(),
            failed=self._failed,
        )

    def _after_correction(self) -> None:
        self._correction.clear()
        self._meeting_selected()

    def _render_overview(self) -> None:
        if self._selected_meeting is None:
            self._overview.setText(self._catalog.text("meetings.no_selection"))
            return
        meeting = self._selected_meeting
        status = _localized(self._catalog, "status", meeting.status)
        self._overview.setText(f"{meeting.title}\n\n{status}\n{meeting.updated_at:%Y-%m-%d %H:%M}")

    def _failed(self, error: Exception) -> None:
        self.state_panel.show_state(
            "offline" if is_engine_offline_error(error) else "error",
            str(error),
        )

    def retranslate(self) -> None:
        tr = self._catalog.text
        self._title.setText(tr("meetings.title"))
        self._filter.setPlaceholderText(tr("meetings.filter"))
        self._meeting_table.setHorizontalHeaderLabels([tr("common.meeting"), tr("common.status")])
        self._segment_table.setHorizontalHeaderLabels(
            [
                tr("common.speaker"),
                tr("common.time"),
                tr("common.raw"),
                tr("common.corrected"),
            ]
        )
        self._insight_table.setHorizontalHeaderLabels(
            [
                tr("common.type"),
                tr("common.title"),
                tr("common.review"),
                tr("common.evidence"),
            ]
        )
        for index, key in enumerate(
            (
                "meetings.overview",
                "meetings.transcript",
                "meetings.insights",
                "meetings.evidence",
            )
        ):
            self._tabs.setTabText(index, tr(key))
        self._save_correction.setText(tr("meetings.save_correction"))
        self._meeting_more.setText(tr("common.load_more"))
        self._detail_more.setText(tr("common.load_more"))
        self._correction.setPlaceholderText(tr("meetings.corrected"))
        self._render_meetings(self._meetings)
        self._render_overview()
        self._render_insights()


def _localized(catalog: LanguageCatalog, group: str, value: str) -> str:
    key = f"{group}.{value}"
    translated = catalog.text(key)
    return value if translated == key else translated
