"""Main window for the companion app."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..services import CollectiveMindGraphCompanionService
from .session_detail_panel import SessionDetailPanel
from .session_list_panel import SessionListPanel
from .widgets import SessionDialog, SummaryBar


class MainWindow(QMainWindow):
    def __init__(self, service: CollectiveMindGraphCompanionService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._selected_session_id: int | None = None

        self.setWindowTitle("Collective MindGraph Companion")
        self.resize(1440, 920)

        self._build_actions()
        self._build_menu()
        self._build_ui()
        self._connect_signals()

        self._refresh_summary()
        self._refresh_sessions()
        self.statusBar().showMessage("Ready", 3000)

    def _build_actions(self) -> None:
        self.new_session_action = QAction("New Session", self)
        self.edit_session_action = QAction("Edit Session", self)
        self.export_action = QAction("Export Session as JSON", self)
        self.exit_action = QAction("Exit", self)
        self.seed_demo_action = QAction("Seed Demo Data", self)
        self.about_action = QAction("About", self)

        self.new_session_action.triggered.connect(lambda: self._run_guarded(self._create_session))
        self.edit_session_action.triggered.connect(lambda: self._run_guarded(self._edit_selected_session))
        self.export_action.triggered.connect(lambda: self._run_guarded(self._export_session))
        self.exit_action.triggered.connect(self.close)
        self.seed_demo_action.triggered.connect(lambda: self._run_guarded(self._seed_demo_data))
        self.about_action.triggered.connect(self._show_about)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.new_session_action)
        file_menu.addAction(self.edit_session_action)
        file_menu.addAction(self.export_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        tools_menu = self.menuBar().addMenu("Tools")
        tools_menu.addAction(self.seed_demo_action)

        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction(self.about_action)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.summary_bar = SummaryBar()
        layout.addWidget(self.summary_bar)

        splitter = QSplitter()
        self.session_list_panel = SessionListPanel()
        self.session_detail_panel = SessionDetailPanel(self._service)
        splitter.addWidget(self.session_list_panel)
        splitter.addWidget(self.session_detail_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([340, 1000])
        layout.addWidget(splitter, 1)

        self.setStatusBar(QStatusBar())

    def _connect_signals(self) -> None:
        self.session_list_panel.search_changed.connect(
            lambda query: self._run_guarded(lambda: self._refresh_sessions(query=query))
        )
        self.session_list_panel.new_session_requested.connect(lambda: self._run_guarded(self._create_session))
        self.session_list_panel.edit_session_requested.connect(
            lambda session_id: self._run_guarded(lambda: self._edit_session(session_id))
        )
        self.session_list_panel.delete_session_requested.connect(
            lambda session_id: self._run_guarded(lambda: self._delete_session(session_id))
        )
        self.session_list_panel.session_selected.connect(
            lambda session_id: self._run_guarded(lambda: self._select_session(session_id))
        )
        self.session_detail_panel.new_session_requested.connect(lambda: self._run_guarded(self._create_session))
        self.session_detail_panel.seed_demo_requested.connect(lambda: self._run_guarded(self._seed_demo_data))
        self.session_detail_panel.session_structure_changed.connect(
            lambda session_id, message: self._run_guarded(
                lambda: self._handle_detail_change(session_id, message)
            )
        )
        self.session_detail_panel.session_selected_from_map.connect(
            lambda session_id: self._run_guarded(lambda: self._select_session(session_id))
        )
        self.session_detail_panel.status_message.connect(
            lambda message: self.statusBar().showMessage(message, 3000)
        )

    def _run_guarded(self, callback: Callable[[], None]) -> None:
        try:
            callback()
        except Exception as exc:  # pragma: no cover - GUI error handling
            QMessageBox.critical(self, "Collective MindGraph Companion", str(exc))
            self.statusBar().showMessage("Operation failed.", 5000)

    def _refresh_summary(self) -> None:
        self.summary_bar.set_summary(self._service.get_app_summary())

    def _refresh_sessions(self, query: str | None = None, selected_id: int | None = None) -> None:
        active_query = self.session_list_panel.search_text() if query is None else query
        sessions = self._service.list_sessions(active_query)
        target_id = selected_id if selected_id is not None else self._selected_session_id
        self.session_list_panel.set_sessions(sessions, target_id)
        if not sessions:
            self._selected_session_id = None
            self.session_detail_panel.set_session(None)
            self.statusBar().showMessage("Create a session or load demo data to get started.", 5000)
        self._sync_action_state(bool(sessions))

    def _select_session(self, session_id: int) -> None:
        self._selected_session_id = session_id
        self.session_detail_panel.set_session(session_id)
        self._sync_action_state(True)
        self.statusBar().showMessage(f"Opened session #{session_id}.", 3000)

    def _create_session(self) -> None:
        dialog = SessionDialog(
            "New Session",
            category_options=self._service.get_category_options(),
            parent=self,
        )
        if dialog.exec() != SessionDialog.DialogCode.Accepted:
            return
        title, main_category, sub_category, template_name, mood = dialog.values()
        session = self._service.create_session(
            title,
            main_category,
            sub_category,
            template_name,
            mood,
        )
        self.session_list_panel.set_search_text("")
        self._refresh_summary()
        self._refresh_sessions(selected_id=session.id)
        self.statusBar().showMessage(f"Created '{session.title}'.", 4000)

    def _edit_selected_session(self) -> None:
        if self._selected_session_id is None:
            QMessageBox.information(self, "Edit Session", "Select a session first.")
            return
        self._edit_session(self._selected_session_id)

    def _edit_session(self, session_id: int) -> None:
        session = self._service.sessions.get(session_id)
        if session is None:
            raise ValueError("Session not found.")
        dialog = SessionDialog(
            "Edit Session",
            category_options=self._service.get_category_options(),
            title=session.title,
            main_category=session.main_category_name,
            sub_category=session.sub_category_name or "",
            template_name=session.template_name,
            mood=session.mood,
            parent=self,
        )
        if dialog.exec() != SessionDialog.DialogCode.Accepted:
            return
        title, main_category, sub_category, template_name, mood = dialog.values()
        updated = self._service.update_session(
            session_id,
            title,
            main_category,
            sub_category,
            template_name,
            mood,
        )
        self._refresh_summary()
        self._refresh_sessions(selected_id=updated.id)
        self.session_detail_panel.set_session(updated.id)
        self.statusBar().showMessage(f"Updated '{updated.title}'.", 4000)

    def _delete_session(self, session_id: int) -> None:
        session = self._service.sessions.get(session_id)
        deleted = self._service.delete_session(session_id)
        if deleted:
            self._refresh_summary()
            if self._selected_session_id == session_id:
                self._selected_session_id = None
            self._refresh_sessions()
            session_name = session.title if session else f"Session #{session_id}"
            self.statusBar().showMessage(f"Deleted '{session_name}'.", 5000)

    def _seed_demo_data(self) -> None:
        sessions = self._service.seed_demo_data()
        selected_id = sessions[0].id if sessions else None
        self.session_list_panel.set_search_text("")
        self._refresh_summary()
        self._refresh_sessions(selected_id=selected_id)
        self.statusBar().showMessage("Demo data is ready.", 5000)

    def _export_session(self) -> None:
        if self._selected_session_id is None:
            QMessageBox.information(self, "Export Session", "Select a session before exporting.")
            return
        session = self._service.sessions.get(self._selected_session_id)
        if session is None:
            raise ValueError("Session not found.")
        default_name = session.title.strip().replace(" ", "_").lower() or f"session_{session.id}"
        default_path = str(Path.home() / "Documents" / f"{default_name}.json")
        file_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Session as JSON",
            default_path,
            "JSON Files (*.json)",
        )
        if not file_path:
            return
        self._service.export_session(session.id, file_path)
        self.statusBar().showMessage(f"Exported session to {file_path}.", 5000)

    def _handle_detail_change(self, session_id: int, message: str) -> None:
        self._selected_session_id = session_id
        self._refresh_summary()
        self._refresh_sessions(selected_id=session_id)
        self.session_detail_panel.set_session(session_id)
        self.statusBar().showMessage(message, 4000)

    def _sync_action_state(self, has_sessions: bool) -> None:
        has_selection = self._selected_session_id is not None
        self.edit_session_action.setEnabled(has_selection)
        self.export_action.setEnabled(has_selection)
        self.session_detail_panel.setEnabled(has_sessions or has_selection)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Collective MindGraph Companion",
            (
                "Collective MindGraph Companion\n\n"
                "A calm local-first desktop app for shaping session flow, branch context, "
                "captured notes, and a readable mindgraph."
            ),
        )
