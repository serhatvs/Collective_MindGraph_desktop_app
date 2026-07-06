"""Rebuilt Native MVP MainWindow with modern 3-area layout."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from dataclasses import asdict

from PySide6.QtCore import Qt, QObject, QThread
from PySide6.QtGui import QAction, QCloseEvent
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
from ..transcription import TranscriptionResult, ReasoningResponse
from .pages.session_overview_page import SessionOverviewPage
from .pages.transcript_page import TranscriptPage
from .pages.insights_page import InsightsPage
from .pages.review_queue_page import ReviewQueuePage
from .pages.knowledge_graph_page import KnowledgeGraphPage
from .pages.reasoning_trace_page import ReasoningTracePage
from .pages.memory_search_page import MemorySearchPage
from .pages.diagnostics_page import DiagnosticsPage
from .session_list_panel import SessionListPanel
from .voice_command_panel import VoiceCommandPanel
from .widgets import SessionDialog
from .workers import BackendTranscriptionWorker


class MainWindow(QMainWindow):
    def __init__(self, service: CollectiveMindGraphService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._selected_session_id: int | None = None
        self._transcription_thread: QThread | None = None
        self._transcription_worker: BackendTranscriptionWorker | None = None

        self.setWindowTitle("Collective MindGraph - Local Technical Memory")
        self.resize(1400, 900)

        self._build_actions()
        self._build_menu()
        self._build_ui()
        self._connect_signals()

        self._refresh_sessions()
        
        status_msg = f"Local-first memory engine - Backend: {self.voice_command_panel.current_transcription_config().base_url}"
        self.statusBar().showMessage(status_msg)
        self.statusBar().addPermanentWidget(QLabel("Collective MindGraph - Native MVP"))

        if os.getenv("CMG_DEBUG_UI_TREE") == "1":
            self.dump_ui_tree()

    def _build_actions(self) -> None:
        self.new_session_action = QAction("New Memory Session", self)
        self.import_action = QAction("Import Knowledge", self)
        self.export_action = QAction("Export Knowledge", self)
        self.exit_action = QAction("Exit", self)
        self.seed_demo_action = QAction("Seed Technical Demo", self)
        self.rebuild_snapshots_action = QAction("Rebuild Memory Index", self)
        self.about_action = QAction("About", self)

        self.new_session_action.triggered.connect(self._create_session)
        self.import_action.triggered.connect(self._import_session)
        self.export_action.triggered.connect(self._export_session)
        self.exit_action.triggered.connect(self.close)
        self.seed_demo_action.triggered.connect(self._seed_demo_data)
        self.rebuild_snapshots_action.triggered.connect(self._rebuild_snapshots)
        self.about_action.triggered.connect(self._show_about)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.new_session_action)
        file_menu.addAction(self.import_action)
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
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Left Sidebar
        self.sidebar_container = QWidget()
        self.sidebar_container.setObjectName("Sidebar")
        self.sidebar_container.setStyleSheet("background: #ffffff; border-right: 1px solid #d6dfe8;")
        self.sidebar_container.setMinimumWidth(320)
        sidebar_layout = QVBoxLayout(self.sidebar_container)
        sidebar_layout.setContentsMargins(16, 16, 16, 16)
        sidebar_layout.setSpacing(12)
        
        app_title = QLabel("Collective Memory")
        app_title.setStyleSheet("font-size: 18pt; font-weight: 700; color: #264a7f; margin-bottom: 8px;")
        sidebar_layout.addWidget(app_title)
        
        status_label = QLabel("Secure Offline Memory")
        status_label.setStyleSheet("color: #19693d; font-weight: 600; margin-bottom: 12px;")
        sidebar_layout.addWidget(status_label)
        
        self.session_list_panel = SessionListPanel()
        sidebar_layout.addWidget(self.session_list_panel, 1)

        root_layout.addWidget(self.sidebar_container)

        # 2. Main Content
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Voice Ingest Header
        self.voice_command_panel = VoiceCommandPanel()
        content_layout.addWidget(self.voice_command_panel)

        # Functional Tabs
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setStyleSheet("QTabBar::tab { padding: 12px 24px; font-weight: 600; }")
        content_layout.addWidget(self.tabs, 1)

        self.overview_page = SessionOverviewPage()
        self.tabs.addTab(self.overview_page, "Session Memory")

        self.transcript_page = TranscriptPage()
        self.tabs.addTab(self.transcript_page, "Knowledge Audit")

        self.insights_page = InsightsPage()
        self.tabs.addTab(self.insights_page, "Reviewed Memory")

        self.review_page = ReviewQueuePage()
        self.tabs.addTab(self.review_page, "Review Suggestions")

        self.graph_page = KnowledgeGraphPage()
        self.tabs.addTab(self.graph_page, "Knowledge Graph")

        self.reasoning_page = ReasoningTracePage()
        self.tabs.addTab(self.reasoning_page, "Reasoning Trace")

        self.memory_search_page = MemorySearchPage()
        self.tabs.addTab(self.memory_search_page, "Global Search")

        self.diagnostics_page = DiagnosticsPage()
        self.tabs.addTab(self.diagnostics_page, "Diagnostics")

        root_layout.addWidget(content_container, 1)
        self.setStatusBar(QStatusBar())

    def _connect_signals(self) -> None:
        self.session_list_panel.session_selected.connect(self._select_session)
        self.session_list_panel.new_session_requested.connect(self._create_session)
        self.session_list_panel.global_search_requested.connect(self._show_memory_search)
        self.session_list_panel.transcribe_file_requested.connect(self._handle_manual_file_ingest)
        
        self.voice_command_panel.transcript_captured.connect(self._ingest_transcript)
        if hasattr(self.voice_command_panel, "backend_health_updated"):
            self.voice_command_panel.backend_health_updated.connect(self.diagnostics_page.set_backend_health)
        self.insights_page.knowledge_item_updated.connect(self._handle_knowledge_update)
        self.review_page.node_approved.connect(self._handle_node_approve)
        self.review_page.node_rejected.connect(self._handle_node_reject)
        self.graph_page.node_updated.connect(self._handle_node_update)
        self.graph_page.source_trace_requested.connect(self._handle_graph_trace)
        self.memory_search_page.source_navigation_requested.connect(self._navigate_to_source)
        self.memory_search_page.reasoning_trace_available.connect(self._handle_reasoning_trace)

    def _handle_node_approve(self, node_id: str) -> None:
        self._service.update_node(node_id, {"review_status": "approved"})
        self.statusBar().showMessage(f"Node Approved: {node_id}")
        self._refresh_current_session_graph()

    def _handle_node_reject(self, node_id: str, reason: str) -> None:
        self._service.update_node(node_id, {"review_status": "rejected", "disabled": True, "disabled_reason": reason})
        self.statusBar().showMessage(f"Node Rejected: {node_id}")
        self._refresh_current_session_graph()

    def _handle_node_update(self, node_id: str, props: dict) -> None:
        self._service.update_node(node_id, props)
        self._refresh_current_session_graph()

    def _handle_graph_trace(self, node_id: str, source_ref_id: str) -> None:
        resolved = self._service.resolve_source_reference(source_ref_id)
        if resolved:
            session_id, segment_id = resolved
            self._navigate_to_source(session_id, segment_id)
            return
        if node_id.startswith("seg_"):
            seg_id = node_id.split("_", 2)[-1]
            if self._selected_session_id:
                self._navigate_to_source(str(self._selected_session_id), seg_id)

    def _handle_reasoning_trace(self, response: ReasoningResponse) -> None:
        # Convert dataclass chains to dict for page
        chains_dict = [asdict(c) for c in response.chains]
        self.reasoning_page.set_reasoning_result(response.query, chains_dict, response.warnings)

    def _refresh_current_session_graph(self) -> None:
        if self._selected_session_id:
            v2_data = self._service.get_session_graph_data(self._selected_session_id)
            self.graph_page.update_graph_data(v2_data["nodes"], v2_data["edges"])
            self.review_page.update_pending_data(v2_data["nodes"])
            self.insights_page.update_reviewed_data(v2_data["nodes"])

    def _handle_knowledge_update(self, item_type: str, original_text: str, new_text: str) -> None:
        if self._selected_session_id is not None:
            success = self._service.update_knowledge_item(
                self._selected_session_id, item_type, original_text, new_text
            )
            if success:
                self.statusBar().showMessage(f"Updated {item_type}: {new_text}")
                self._refresh_current_session_graph()
            else:
                QMessageBox.warning(self, "Update Error", f"Failed to persist update for {item_type}.")

    def _refresh_sessions(self, selected_id: int | None = None) -> None:
        sessions = self._service.list_sessions()
        self.session_list_panel.set_sessions(sessions, selected_id or self._selected_session_id)
        
        vector_count = self._service.vector_repo.get_count()
        dim = self._service.embedding_provider.dimension
        provider_name = self._service.embedding_provider.__class__.__name__.replace("EmbeddingProvider", "")
        model_path = getattr(self._service.embedding_provider, "_model_path", "")
        self.diagnostics_page.set_app_summary(vector_count, dim, provider_name, model_path)

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

    def _rebuild_snapshots(self) -> None:
        rebuilt = self._service.rebuild_snapshots(self._selected_session_id)
        self._refresh_sessions()
        scope = "selected session" if self._selected_session_id is not None else "all sessions"
        self.statusBar().showMessage(f"Rebuilt {len(rebuilt)} memory index snapshot(s) for {scope}.")

    def _show_about(self) -> None:
        QMessageBox.about(self, "About Collective MindGraph", "Native MVP UI - Local-First Technical Memory")

    def _ingest_transcript(self, result: TranscriptionResult) -> None:
        session = self._service.ingest_transcription_result(result, self._selected_session_id)
        self._refresh_sessions(selected_id=session.id)
        self._select_session(session.id)

    def _handle_manual_file_ingest(self) -> None:
        if self._transcription_thread is not None:
            QMessageBox.warning(self, "Transcription in Progress", "Another file is currently being processed.")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Open Audio File for Memory Extraction", 
            "", 
            "Audio Files (*.wav *.mp3 *.flac *.m4a)"
        )
        if not file_path:
            return

        config = self.voice_command_panel.current_transcription_config()
        self.statusBar().showMessage(f"Extracting memory from {Path(file_path).name} locally...")
        
        self._transcription_thread = QThread(self)
        self._transcription_worker = BackendTranscriptionWorker(file_path, config)
        self._transcription_worker.moveToThread(self._transcription_thread)
        
        self._transcription_thread.started.connect(self._transcription_worker.run)
        self._transcription_worker.finished.connect(self._handle_file_transcription_finished)
        self._transcription_worker.failed.connect(self._handle_file_transcription_failed)
        self._transcription_worker.progress_updated.connect(self._handle_worker_progress)
        self._transcription_worker.finished.connect(self._transcription_thread.quit)
        self._transcription_worker.failed.connect(self._transcription_thread.quit)
        self._transcription_thread.finished.connect(self._cleanup_transcription_worker)
        
        self._transcription_thread.start()

    def _handle_worker_progress(self, progress: int, message: str) -> None:
        self.statusBar().showMessage(f"[{progress}%] {message}")

    def _handle_file_transcription_finished(self, result: TranscriptionResult) -> None:
        self.statusBar().showMessage("Memory extraction complete.")
        self._ingest_transcript(result)
        QMessageBox.information(self, "Extraction Success", "File processed and added to memory.")

    def _handle_file_transcription_failed(self, error: str) -> None:
        self.statusBar().showMessage("Memory extraction failed.")
        QMessageBox.critical(self, "Extraction Error", f"Failed to extract memory from file:\n{error}")

    def _cleanup_transcription_worker(self) -> None:
        self._transcription_thread = None
        self._transcription_worker = None

    def _export_session(self) -> None:
        if self._selected_session_id is None:
            QMessageBox.warning(self, "Export Knowledge", "Please select a memory session to export first.")
            return

        detail = self._service.get_session_detail(self._selected_session_id)
        if not detail:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Export Knowledge to JSON", 
            f"MindGraph_{detail.session.title.replace(' ', '_')}.json", 
            "JSON Files (*.json)"
        )
        if not file_path:
            return

        try:
            self._service.export_session(self._selected_session_id, file_path)
            QMessageBox.information(self, "Export Knowledge", f"Knowledge successfully exported to:\n{file_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", f"Failed to export knowledge:\n{str(exc)}")

    def _import_session(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Knowledge JSON", "", "JSON Files (*.json)")
        if file_path:
            try:
                session = self._service.import_session(file_path)
                self._refresh_sessions(selected_id=session.id)
                QMessageBox.information(self, "Import Success", f"Knowledge session '{session.title}' imported successfully.")
            except Exception as exc:
                QMessageBox.critical(self, "Import Error", f"Failed to import knowledge:\n{str(exc)}")

    def _select_session(self, session_id: int) -> None:
        self._selected_session_id = session_id
        detail = self._service.get_session_detail(session_id)
        if detail:
            self.overview_page.set_detail(detail)
            self.transcript_page.set_detail(detail)
            self.insights_page.set_detail(detail)
            self.diagnostics_page.set_detail(detail)
            
            # Refresh V2 tabs
            self._refresh_current_session_graph()
            
            self.tabs.setCurrentWidget(self.overview_page)
            self.statusBar().showMessage(f"Memory Loaded: {detail.session.title}")

    def _show_memory_search(self) -> None:
        self.memory_search_page.set_config(self.voice_command_panel.current_transcription_config())
        self.tabs.setCurrentWidget(self.memory_search_page)

    def _navigate_to_source(self, session_id_str: str, segment_id: str) -> None:
        try:
            session_id = int(session_id_str)
        except (TypeError, ValueError):
            QMessageBox.warning(self, "Open Source", "The selected source does not point to a local session.")
            return
        if session_id != self._selected_session_id:
            self._select_session(session_id)
        
        self.tabs.setCurrentWidget(self.transcript_page)
        if segment_id:
            self.transcript_page.scroll_to_segment(segment_id)

    def dump_ui_tree(self) -> None:
        print("\n--- UI TREE DUMP ---")
        def _dump(obj, indent=0):
            name = obj.objectName() or "unnamed"
            print(f"{'  ' * indent}{obj.__class__.__name__} ({name})")
            for child in obj.children():
                if isinstance(child, QObject):
                    _dump(child, indent + 1)
        _dump(self)
        print("--- END UI DUMP ---\n")

    def closeEvent(self, event: QCloseEvent) -> None:
        if hasattr(self.voice_command_panel, "shutdown"):
            self.voice_command_panel.shutdown()
        super().closeEvent(event)
