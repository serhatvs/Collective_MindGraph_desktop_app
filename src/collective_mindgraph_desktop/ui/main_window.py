"""Rebuilt Native MVP MainWindow with modern 3-area layout."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..models import TranscriptAnalysisSegment, SessionDetail
from ..services import CollectiveMindGraphService
from ..transcription import TranscriptionResult
from .pages.session_overview_page import SessionOverviewPage
from .pages.transcript_page import TranscriptPage
from .pages.insights_page import InsightsPage
from .pages.memory_search_page import MemorySearchPage
from .pages.diagnostics_page import DiagnosticsPage
from .session_list_panel import SessionListPanel
from .voice_command_panel import VoiceCommandPanel
from .widgets import SessionDialog


class MainWindow(QMainWindow):
    def __init__(self, service: CollectiveMindGraphService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._selected_session_id: int | None = None

        self.setWindowTitle("Collective MindGraph — Native MVP UI")
        self.resize(1400, 900)

        self._build_actions()
        self._build_menu()
        self._build_ui()
        self._connect_signals()

        self._refresh_sessions()
        
        status_msg = f"Local-first desktop frontend • Backend: {self.voice_command_panel.current_transcription_config().base_url}"
        self.statusBar().showMessage(status_msg)
        self.statusBar().addPermanentWidget(QLabel("Collective MindGraph Desktop — New MVP UI"))

        if os.getenv("CMG_DEBUG_UI_TREE") == "1":
            self.dump_ui_tree()

    def _build_actions(self) -> None:
        self.new_session_action = QAction("New Session", self)
        self.export_action = QAction("Export Session", self)
        self.exit_action = QAction("Exit", self)
        self.seed_demo_action = QAction("Seed Technical Demo", self)
        self.rebuild_snapshots_action = QAction("Rebuild Index", self)
        self.about_action = QAction("About", self)

        self.new_session_action.triggered.connect(self._create_session)
        self.export_action.triggered.connect(self._export_session)
        self.exit_action.triggered.connect(self.close)
        self.seed_demo_action.triggered.connect(self._seed_demo_data)
        self.rebuild_snapshots_action.triggered.connect(self._rebuild_snapshots)
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
        
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Left Sidebar
        self.sidebar_container = QWidget()
        self.sidebar_container.setObjectName("Sidebar")
        self.sidebar_container.setStyleSheet("background: #ffffff; border-right: 1px solid #d6dfe8;")
        self.sidebar_container.setMinimumWidth(320)
        sidebar_layout = QVBoxLayout(self.sidebar_container)
        sidebar_layout.setContentsMargins(16, 16, 16, 16)
        sidebar_layout.setSpacing(12)
        
        app_title = QLabel("MindGraph")
        app_title.setStyleSheet("font-size: 18pt; font-weight: 700; color: #264a7f; margin-bottom: 8px;")
        sidebar_layout.addWidget(app_title)
        
        status_label = QLabel("● Offline Mode (Local)")
        status_label.setStyleSheet("color: #19693d; font-weight: 600; margin-bottom: 12px;")
        sidebar_layout.addWidget(status_label)
        
        self.session_list_panel = SessionListPanel()
        sidebar_layout.addWidget(self.session_list_panel, 1)
        
        # 2. Main Content Area
        self.content_container = QWidget()
        content_layout = QVBoxLayout(self.content_container)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)

        # Voice command stays on top for quick capture
        self.voice_command_panel = VoiceCommandPanel()
        content_layout.addWidget(self.voice_command_panel)

        # Functional Tabs
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setStyleSheet("QTabBar::tab { padding: 12px 24px; font-weight: 600; }")
        content_layout.addWidget(self.tabs, 1)

        self.overview_page = SessionOverviewPage()
        self.tabs.addTab(self.overview_page, "Session Overview")

        self.transcript_page = TranscriptPage()
        self.tabs.addTab(self.transcript_page, "Transcript")

        self.insights_page = InsightsPage()
        self.tabs.addTab(self.insights_page, "Insights")

        self.memory_search_page = MemorySearchPage()
        self.tabs.addTab(self.memory_search_page, "Memory Search")

        self.diagnostics_page = DiagnosticsPage()
        self.tabs.addTab(self.diagnostics_page, "Diagnostics")

        # Layout integration
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.sidebar_container)
        splitter.addWidget(self.content_container)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 1080])
        main_layout.addWidget(splitter)

        self.setStatusBar(QStatusBar())

    def _connect_signals(self) -> None:
        self.session_list_panel.session_selected.connect(self._select_session)
        self.session_list_panel.new_session_requested.connect(self._create_session)
        self.session_list_panel.global_search_requested.connect(self._show_memory_search)
        self.session_list_panel.transcribe_file_requested.connect(self._handle_manual_file_ingest)
        
        self.voice_command_panel.transcript_captured.connect(self._ingest_transcript)
        self.memory_search_page.source_navigation_requested.connect(self._navigate_to_source)

    def _handle_manual_file_ingest(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Audio File", "", "Audio Files (*.wav *.mp3 *.flac)")
        if file_path:
            QMessageBox.information(self, "Transcribe File", f"Selected: {file_path}. Processing will start locally.")

    def _select_session(self, session_id: int) -> None:
        self._selected_session_id = session_id
        detail = self._service.get_session_detail(session_id)
        if detail:
            self.overview_page.set_detail(detail)
            self.transcript_page.set_detail(detail)
            self.insights_page.set_detail(detail)
            self.diagnostics_page.set_detail(detail)
            self.tabs.setCurrentWidget(self.overview_page)
            self.statusBar().showMessage(f"Viewing Session: {detail.session.title}")

    def _show_memory_search(self) -> None:
        self.memory_search_page.set_config(self.voice_command_panel.current_transcription_config())
        self.tabs.setCurrentWidget(self.memory_search_page)

    def _navigate_to_source(self, session_id_str: str, segment_id: str) -> None:
        try:
            if session_id_str.isdigit():
                session_id = int(session_id_str)
            else:
                session_id = self._service.find_session_by_conversation_id(session_id_str)
                if session_id is None:
                    raise ValueError(f"Session {session_id_str} not found.")
            
            self._select_session(session_id)
            if segment_id:
                self.tabs.setCurrentWidget(self.transcript_page)
                self.transcript_page.scroll_to_segment(segment_id)
        except Exception as exc:
            QMessageBox.warning(self, "Navigation Error", str(exc))

    def _create_session(self) -> None:
        dialog = SessionDialog(self)
        if dialog.exec() == SessionDialog.DialogCode.Accepted:
            title, dev_id, status = dialog.values()
            session = self._service.create_session(title, dev_id, status)
            self._refresh_sessions(selected_id=session.id)

    def _seed_demo_data(self) -> None:
        self._service.seed_demo_data()
        self._refresh_sessions()
        self.statusBar().showMessage("Demo data loaded.")

    def _refresh_sessions(self, selected_id: int | None = None) -> None:
        sessions = self._service.list_sessions()
        self.session_list_panel.set_sessions(sessions, selected_id or self._selected_session_id)

    def _ingest_transcript(self, result: TranscriptionResult) -> None:
        session = self._service.ingest_transcription_result(result, self._selected_session_id)
        self._refresh_sessions(selected_id=session.id)
        self._select_session(session.id)

    def _export_session(self) -> None:
        pass

    def _rebuild_snapshots(self) -> None:
        pass

    def _show_about(self) -> None:
        QMessageBox.about(self, "About Collective MindGraph", "Native MVP UI - Local-First Technical Memory")

    def dump_ui_tree(self) -> None:
        print("\n--- UI WIDGET TREE DUMP ---")
        def _dump(obj: QObject, indent: int = 0):
            name = obj.objectName() or "unnamed"
            print(f"{'  ' * indent}{obj.__class__.__name__} ({name})")
            for child in obj.children():
                if isinstance(child, QObject):
                    _dump(child, indent + 1)
        _dump(self)
        print("--- END UI DUMP ---\n")
