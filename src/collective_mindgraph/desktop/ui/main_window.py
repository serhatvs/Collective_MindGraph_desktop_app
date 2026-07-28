"""Six-workspace PySide6 product shell."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..contracts import DashboardSnapshot, EngineHealth
from ..engine_client import EngineClient, EngineClientError
from ..engine_runtime import LocalEngineManager
from ..language_catalog import LanguageCatalog
from ..preferences import DesktopPreferenceStore
from .job_presenter import JobPresenter
from .workspaces import (
    CaptureWorkspace,
    DashboardWorkspace,
    KnowledgeWorkspace,
    MeetingsWorkspace,
    MemoryWorkspace,
    SettingsWorkspace,
)


class MainWindow(QMainWindow):
    def __init__(
        self,
        client: EngineClient | None = None,
        catalog: LanguageCatalog | None = None,
        engine_manager: LocalEngineManager | None = None,
        auto_start_engine: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._client = client or EngineClient()
        self._catalog = catalog or LanguageCatalog()
        self._engine_manager = engine_manager or LocalEngineManager(self)
        self._presenter = JobPresenter(self)
        self._preferences = DesktopPreferenceStore()
        self._auto_start_engine = auto_start_engine
        self._startup_attempted = False
        self.setMinimumSize(1120, 720)
        self.resize(1360, 850)

        canvas = QWidget()
        canvas.setObjectName("AppCanvas")
        root = QHBoxLayout(canvas)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        navigation = QFrame()
        navigation.setObjectName("Navigation")
        navigation.setFixedWidth(210)
        nav_layout = QVBoxLayout(navigation)
        nav_layout.setContentsMargins(14, 20, 14, 18)
        brand = QLabel("Collective\nMindGraph")
        brand.setStyleSheet("color: white; font-size: 20px; font-weight: 750")
        nav_layout.addWidget(brand)
        nav_layout.addSpacing(24)
        self._buttons = QButtonGroup(self)
        self._buttons.setExclusive(True)
        self._nav_buttons: list[QPushButton] = []
        self._stack = QStackedWidget()

        self.dashboard = DashboardWorkspace(self._catalog)
        self.capture = CaptureWorkspace(
            self._client,
            self._catalog,
            self._presenter,
            self._preferences,
        )
        self.meetings = MeetingsWorkspace(
            self._client,
            self._catalog,
            self._presenter,
        )
        self.memory = MemoryWorkspace(
            self._client,
            self._catalog,
            self._presenter,
        )
        self.knowledge = KnowledgeWorkspace(
            self._client,
            self._catalog,
            self._presenter,
        )
        self.settings = SettingsWorkspace(
            self._client,
            self._catalog,
            self._presenter,
            self._preferences,
        )
        self._workspaces = (
            self.dashboard,
            self.capture,
            self.meetings,
            self.memory,
            self.knowledge,
            self.settings,
        )
        self._nav_keys = (
            "nav.dashboard",
            "nav.capture",
            "nav.meetings",
            "nav.memory",
            "nav.knowledge",
            "nav.settings",
        )
        for index, workspace in enumerate(self._workspaces):
            button = QPushButton()
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, target=index: self.show_workspace(target))
            self._buttons.addButton(button, index)
            self._nav_buttons.append(button)
            nav_layout.addWidget(button)
            self._stack.addWidget(workspace)
        nav_layout.addStretch()
        self._engine_badge = QLabel()
        self._engine_badge.setStyleSheet("color: #AAB9D2; padding: 8px")
        self._engine_badge.setWordWrap(True)
        nav_layout.addWidget(self._engine_badge)
        root.addWidget(navigation)
        root.addWidget(self._stack, 1)
        self.setCentralWidget(canvas)
        self._nav_buttons[0].setChecked(True)

        self.dashboard.capture_requested.connect(lambda: self.show_workspace(1))
        self.dashboard.file_requested.connect(self._choose_capture_file)
        self.dashboard.ask_requested.connect(self._ask_from_dashboard)
        self.dashboard.meeting_requested.connect(self._show_meeting)
        self.dashboard.refresh_requested.connect(self.refresh_dashboard)
        self.capture.meeting_ready.connect(self._show_meeting)
        self._catalog.language_changed.connect(self.retranslate)
        self._engine_manager.state_changed.connect(self._engine_badge.setText)
        self._engine_manager.error_occurred.connect(self._engine_badge.setText)
        self.retranslate()
        QTimer.singleShot(0, self.refresh_dashboard)

    def show_workspace(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        if 0 <= index < len(self._nav_buttons):
            self._nav_buttons[index].setChecked(True)
        if index == 2:
            self.meetings.refresh()
        elif index == 4:
            self.knowledge.refresh()
        elif index == 5:
            self.settings.refresh()

    def refresh_dashboard(self) -> None:
        self.dashboard.state_panel.show_state("loading")
        self._presenter.submit(
            lambda: (self._client.dashboard(), self._client.health()),
            succeeded=self._dashboard_loaded,
            failed=self._dashboard_failed,
        )

    def _dashboard_loaded(self, value: object) -> None:
        snapshot, health = value
        assert isinstance(snapshot, DashboardSnapshot)
        assert isinstance(health, EngineHealth)
        self.dashboard.update_snapshot(snapshot, health)
        self._engine_badge.setText(
            f"{self._catalog.text('dashboard.engine')}: "
            f"{self._catalog.text(f'status.{health.status}')}"
        )

    def _dashboard_failed(self, error: Exception) -> None:
        offline = isinstance(error, EngineClientError)
        self.dashboard.show_error(str(error), offline=offline)
        if offline and self._auto_start_engine and not self._startup_attempted:
            self._startup_attempted = True
            if self._engine_manager.ensure_running(self._client.settings.base_url):
                QTimer.singleShot(1200, self.refresh_dashboard)

    def _ask_from_dashboard(self, query: str) -> None:
        if not query:
            return
        self.show_workspace(3)
        self.memory.set_query_and_ask(query)

    def _show_meeting(self, meeting_id: int) -> None:
        self.show_workspace(2)
        self.meetings.select_meeting(meeting_id)

    def _choose_capture_file(self) -> None:
        self.show_workspace(1)
        self.capture.choose_file()

    def retranslate(self) -> None:
        self.setWindowTitle(self._catalog.text("app.title"))
        for button, key in zip(self._nav_buttons, self._nav_keys, strict=True):
            button.setText(self._catalog.text(key))

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override
        self._engine_manager.shutdown()
        event.accept()
