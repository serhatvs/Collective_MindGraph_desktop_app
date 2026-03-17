"""Main application window."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..models import TranscriptAnalysisSegment
from ..services import CollectiveMindGraphService
from ..transcription import TranscriptionResult
from .session_detail_panel import SessionDetailPanel
from .session_list_panel import SessionListPanel
from .voice_command_panel import VoiceCommandPanel
from .widgets import SessionDialog


class MainWindow(QMainWindow):
    def __init__(self, service: CollectiveMindGraphService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._selected_session_id: int | None = None

        self.setWindowTitle("Collective MindGraph")
        self.resize(1360, 860)

        self._build_actions()
        self._build_menu()
        self._build_ui()
        self._connect_signals()

        self._refresh_summary()
        self._refresh_sessions()
        self.statusBar().showMessage("Ready", 3000)

    def _build_actions(self) -> None:
        self.new_session_action = QAction("New Session", self)
        self.export_action = QAction("Export Session as JSON", self)
        self.exit_action = QAction("Exit", self)
        self.seed_demo_action = QAction("Seed Demo Data", self)
        self.rebuild_snapshots_action = QAction("Rebuild Snapshots", self)
        self.about_action = QAction("About", self)

        self.new_session_action.triggered.connect(lambda: self._run_guarded(self._create_session))
        self.export_action.triggered.connect(lambda: self._run_guarded(self._export_session))
        self.exit_action.triggered.connect(self.close)
        self.seed_demo_action.triggered.connect(lambda: self._run_guarded(self._seed_demo_data))
        self.rebuild_snapshots_action.triggered.connect(lambda: self._run_guarded(self._rebuild_snapshots))
        self.about_action.triggered.connect(self._show_about)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.new_session_action)
        file_menu.addAction(self.export_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        tools_menu = self.menuBar().addMenu("Tools")
        tools_menu.addAction(self.seed_demo_action)
        tools_menu.addAction(self.rebuild_snapshots_action)

        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction(self.about_action)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        self.session_list_panel = SessionListPanel()

        content_host = QWidget()
        content_layout = QVBoxLayout(content_host)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        self.voice_command_panel = VoiceCommandPanel()
        content_layout.addWidget(self.voice_command_panel)

        self.session_detail_panel = SessionDetailPanel()
        self.session_detail_panel.hide()
        content_layout.addWidget(self.session_detail_panel, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.session_list_panel)
        splitter.addWidget(content_host)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 1040])
        layout.addWidget(splitter, 1)

        self.setStatusBar(QStatusBar())

    def _connect_signals(self) -> None:
        self.session_list_panel.search_changed.connect(
            lambda query: self._run_guarded(lambda: self._refresh_sessions(query=query))
        )
        self.session_list_panel.new_session_requested.connect(
            lambda: self._run_guarded(self._create_session)
        )
        self.session_list_panel.delete_session_requested.connect(
            lambda session_id: self._run_guarded(lambda: self._delete_session(session_id))
        )
        self.session_list_panel.session_selected.connect(
            lambda session_id: self._run_guarded(lambda: self._select_session(session_id))
        )
        self.voice_command_panel.activity_reported.connect(
            lambda message: self.statusBar().showMessage(message, 5000)
        )
        self.voice_command_panel.transcript_captured.connect(
            lambda result: self._run_guarded(
                lambda: self._ingest_transcript(result)
            )
        )
        self.session_detail_panel.analysis_corrections_requested.connect(
            lambda transcript_id, segments: self._run_guarded(
                lambda: self._save_analysis_corrections(transcript_id, segments)
            )
        )

    def _run_guarded(self, callback: Callable[[], None]) -> None:
        try:
            callback()
        except Exception as exc:  # pragma: no cover - GUI error handling
            QMessageBox.critical(self, "Collective MindGraph", str(exc))
            self.statusBar().showMessage("Operation failed", 5000)

    def _refresh_summary(self) -> None:
        return

    def _refresh_sessions(self, query: str | None = None, selected_id: int | None = None) -> None:
        active_query = self.session_list_panel.search_text() if query is None else query
        sessions = self._service.list_sessions(active_query)
        target_id = selected_id if selected_id is not None else self._selected_session_id
        self.session_list_panel.set_sessions(sessions, target_id)
        current_session_id = self.session_list_panel.current_session_id()
        if current_session_id is None:
            self._selected_session_id = None
            self.session_detail_panel.set_detail(None)
            self.session_detail_panel.hide()
        if not sessions:
            self._selected_session_id = None
            self.session_detail_panel.set_detail(None)
            self.session_detail_panel.hide()
            self.statusBar().showMessage("Create a session or seed demo data to get started.", 5000)
        self._sync_action_state(bool(sessions))

    def _select_session(self, session_id: int) -> None:
        self._selected_session_id = session_id
        self.session_detail_panel.set_detail(self._service.get_session_detail(session_id))
        self.session_detail_panel.show()
        self._sync_action_state(True)
        self.statusBar().showMessage(f"Loaded session #{session_id}", 3000)

    def _create_session(self) -> None:
        dialog = SessionDialog(self)
        if dialog.exec() != SessionDialog.DialogCode.Accepted:
            return
        title, device_id, status = dialog.values()
        session = self._service.create_session(title, device_id, status)
        self.session_list_panel.set_search_text("")
        self._refresh_summary()
        self._refresh_sessions(selected_id=session.id)
        self.statusBar().showMessage(f"Created session '{session.title}'", 4000)

    def _delete_session(self, session_id: int) -> None:
        detail = self._service.get_session_detail(session_id)
        deleted = self._service.delete_session(session_id)
        if deleted:
            self._refresh_summary()
            self._selected_session_id = None if self._selected_session_id == session_id else self._selected_session_id
            self._refresh_sessions()
            session_name = detail.session.title if detail else f"#{session_id}"
            self.statusBar().showMessage(f"Deleted session '{session_name}'", 5000)

    def _seed_demo_data(self) -> None:
        sessions = self._service.seed_demo_data()
        selected_id = sessions[0].id if sessions else None
        self.session_list_panel.set_search_text("")
        self._refresh_summary()
        self._refresh_sessions(selected_id=selected_id)
        self.statusBar().showMessage("Demo data ready", 5000)

    def _rebuild_snapshots(self) -> None:
        rebuilt = self._service.rebuild_snapshots(self._selected_session_id)
        self._refresh_summary()
        self._refresh_sessions(selected_id=self._selected_session_id)
        if rebuilt:
            scope = "selected session" if self._selected_session_id is not None else "all sessions"
            self.statusBar().showMessage(f"Rebuilt snapshots for {scope}", 5000)
        else:
            self.statusBar().showMessage("No sessions available for snapshot rebuild", 5000)

    def _export_session(self) -> None:
        if self._selected_session_id is None:
            QMessageBox.information(self, "Export Session", "Select a session before exporting.")
            return

        detail = self._service.get_session_detail(self._selected_session_id)
        if detail is None:
            raise ValueError("Selected session was not found.")

        default_name = detail.session.title.strip().replace(" ", "_").lower() or f"session_{detail.session.id}"
        default_path = str(Path.home() / "Documents" / f"{default_name}.json")
        file_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Session as JSON",
            default_path,
            "JSON Files (*.json)",
        )
        if not file_path:
            return
        self._service.export_session(detail.session.id, file_path)
        self.statusBar().showMessage(f"Exported session to {file_path}", 5000)

    def _ingest_transcript(self, result: TranscriptionResult) -> None:
        had_selection = self._selected_session_id is not None
        session = self._service.ingest_transcription_result(result, self._selected_session_id)
        self.session_list_panel.set_search_text("")
        self._refresh_summary()
        self._refresh_sessions(selected_id=session.id)
        if had_selection:
            self.statusBar().showMessage(
                f"Added transcript to '{session.title}'"
                + (f" ({result.speaker_count} speakers)" if result.speaker_count else ""),
                5000,
            )
            return
        self.statusBar().showMessage(
            f"Started new session '{session.title}' from transcript"
            + (f" ({result.speaker_count} speakers)" if result.speaker_count else ""),
            5000,
        )

    def _save_analysis_corrections(
        self,
        transcript_id: int,
        segments: list[TranscriptAnalysisSegment],
    ) -> None:
        self._service.save_transcript_analysis_corrections(transcript_id, segments)
        selected_id = self._selected_session_id
        self._refresh_summary()
        self._refresh_sessions(selected_id=selected_id)
        self.statusBar().showMessage("Transcript corrections saved.", 5000)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Collective MindGraph",
            (
                "Collective MindGraph\n\n"
                "Native PySide6 desktop application for exploring local reasoning sessions, "
                "transcript timelines, graph trees, and snapshot history."
            ),
        )

    def _sync_action_state(self, has_sessions: bool) -> None:
        self.export_action.setEnabled(self._selected_session_id is not None)
        self.rebuild_snapshots_action.setEnabled(has_sessions)
