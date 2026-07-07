"""Rebuilt Native MVP MainWindow with modern 3-area layout."""

from __future__ import annotations

import os
import logging
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
from ..transcription import EvidenceChain, EvidenceStep, MemoryAskResponse, TranscriptionResult, ReasoningResponse
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


LOGGER = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, service: CollectiveMindGraphService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._selected_session_id: int | None = None
        self._transcription_thread: QThread | None = None
        self._transcription_worker: BackendTranscriptionWorker | None = None

        self.setWindowTitle("Collective MindGraph — Local Technical Memory")
        self.resize(1400, 900)

        self._build_actions()
        self._build_menu()
        self._build_ui()
        self._connect_signals()

        self._refresh_sessions()
        
        status_msg = f"Local-first memory engine • Backend: {self.voice_command_panel.current_transcription_config().base_url}"
        self.statusBar().showMessage(status_msg)
        self.statusBar().addPermanentWidget(QLabel("Collective MindGraph — Native MVP"))

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
        
        status_label = QLabel("Local-First Memory")
        status_label.setStyleSheet("color: #19693d; font-weight: 600; margin-bottom: 12px;")
        sidebar_layout.addWidget(status_label)

        self.alpha_limitations_label = QLabel(
            "Friend alpha: Turkish-first local transcription. No speaker separation yet. "
            "Ask answers use available evidence; local LLM is optional."
        )
        self.alpha_limitations_label.setWordWrap(True)
        self.alpha_limitations_label.setStyleSheet(
            "color: #5a6b7d; background: #f8fbff; border: 1px solid #d6dfe8; "
            "border-radius: 6px; padding: 8px;"
        )
        sidebar_layout.addWidget(self.alpha_limitations_label)
        
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
        self.tabs.addTab(self.insights_page, "Extracted Notes")

        self.review_page = ReviewQueuePage()
        self.tabs.addTab(self.review_page, "Review Suggestions")

        self.graph_page = KnowledgeGraphPage()
        self.tabs.addTab(self.graph_page, "Knowledge Graph")

        self.reasoning_page = ReasoningTracePage()
        self.tabs.addTab(self.reasoning_page, "Reasoning Trace")

        self.memory_search_page = MemorySearchPage()
        self.memory_search_page.set_config(self.voice_command_panel.current_transcription_config())
        self.memory_search_page.ask_panel.set_local_fallback_provider(self._ask_selected_session_locally)
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
        self.session_list_panel.export_session_requested.connect(self._export_session)
        self.session_list_panel.delete_session_requested.connect(self._delete_session)
        self.session_list_panel.search_changed.connect(lambda _query: self._refresh_sessions())
        self.session_list_panel.seed_demo_requested.connect(self._seed_demo_data)
        
        self.voice_command_panel.transcript_captured.connect(self._ingest_transcript)
        backend_health_signal = getattr(self.voice_command_panel, "backend_health_updated", None)
        if backend_health_signal is not None:
            backend_health_signal.connect(self.diagnostics_page.set_backend_health)
        self.insights_page.knowledge_item_updated.connect(self._handle_knowledge_update)
        self.review_page.node_approved.connect(self._handle_node_approve)
        self.review_page.node_rejected.connect(self._handle_node_reject)
        self.graph_page.node_updated.connect(self._handle_node_update)
        self.graph_page.node_merge_requested.connect(self._handle_node_merge)
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

    def _handle_node_merge(self, source_node_id: str, target_node_id: str) -> None:
        if self._service.merge_nodes(source_node_id, target_node_id):
            self.statusBar().showMessage(f"Node Merged: {source_node_id} -> {target_node_id}")
            self._refresh_current_session_graph()
        else:
            QMessageBox.warning(self, "Merge Failed", "Could not merge the selected nodes.")

    def _handle_graph_trace(self, session_id: str, segment_id: str) -> None:
        resolved_session_id = session_id or (str(self._selected_session_id) if self._selected_session_id else "")
        if resolved_session_id:
            self._navigate_to_source(resolved_session_id, segment_id)

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
        sessions = self._service.list_sessions(self.session_list_panel.search_text())
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

    def _delete_session(self, session_id: int) -> None:
        deleted = self._service.delete_session(session_id)
        if not deleted:
            QMessageBox.warning(self, "Delete Session", "The selected session could not be found.")
            self._refresh_sessions()
            return

        if self._selected_session_id == session_id:
            self._selected_session_id = None
            self._clear_session_pages()

        self._refresh_sessions()
        self.statusBar().showMessage("Memory session deleted.")

    def _seed_demo_data(self) -> None:
        self._service.seed_demo_data()
        self._refresh_sessions()
        self.statusBar().showMessage("Demo data loaded.")

    def _rebuild_snapshots(self) -> None:
        pass

    def _show_about(self) -> None:
        QMessageBox.about(self, "About Collective MindGraph", "Native MVP UI - Local-First Technical Memory")

    def _ingest_transcript(self, result: TranscriptionResult):
        session = self._service.ingest_transcription_result(result, self._selected_session_id)
        self._refresh_sessions(selected_id=session.id)
        self._select_session(session.id)
        return session

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
        self.statusBar().showMessage(f"Transcribing {Path(file_path).name} locally...")
        self.session_list_panel.set_transcription_busy(True)
        
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
        try:
            self._ingest_transcript(result)
        except Exception as exc:
            LOGGER.exception("Failed to persist transcription result.")
            self._handle_file_transcription_failed(f"Transcript was created, but could not be saved: {exc}")
            return
        self.tabs.setCurrentWidget(self.transcript_page)
        self.statusBar().showMessage("Transcript ready. Extracted notes are available in Extracted Notes.")
        QMessageBox.information(
            self,
            "Transcript Ready",
            "The audio file was transcribed and added to the selected session.",
        )

    def _handle_file_transcription_failed(self, error: str) -> None:
        LOGGER.error("Local file transcription failed: %s", error)
        self.statusBar().showMessage("Local file transcription failed.")
        QMessageBox.critical(
            self,
            "Transcription Error",
            "Could not transcribe this audio file.\n\n"
            "Try again after the local backend finishes starting. You can also check Settings for the "
            "backend URL and confirm the file contains audible speech.\n\n"
            f"Details:\n{error}",
        )

    def _cleanup_transcription_worker(self) -> None:
        self._transcription_thread = None
        self._transcription_worker = None
        self.session_list_panel.set_transcription_busy(False)

    def _export_session(self) -> None:
        if self._selected_session_id is None:
            QMessageBox.warning(self, "Export Knowledge", "Please select a memory session to export first.")
            return

        detail = self._service.get_session_detail(self._selected_session_id)
        if not detail:
            QMessageBox.warning(self, "Export Knowledge", "The selected session could not be found.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Export Knowledge to JSON", 
            f"MindGraph_{detail.session.title.replace(' ', '_')}.json", 
            "JSON Files (*.json)"
        )
        if not file_path:
            return
        export_path = Path(file_path)
        if export_path.suffix.lower() != ".json":
            export_path = export_path.with_suffix(".json")

        try:
            self._service.export_session(self._selected_session_id, export_path)
            self.statusBar().showMessage(f"Session exported to {export_path}")
            QMessageBox.information(self, "Export Knowledge", f"Session exported to:\n{export_path}")
        except Exception as exc:
            LOGGER.exception("Session export failed.")
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

    def _select_session(self, session_id: int) -> bool:
        detail = self._service.get_session_detail(session_id)
        if not detail:
            self.statusBar().showMessage(f"Memory session not found: {session_id}")
            return False

        self._selected_session_id = session_id
        self.overview_page.set_detail(detail)
        self.transcript_page.set_detail(detail)
        self.insights_page.set_detail(detail)
        self.diagnostics_page.set_detail(detail)

        # Refresh V2 tabs
        self._refresh_current_session_graph()

        self.tabs.setCurrentWidget(self.overview_page)
        self.statusBar().showMessage(f"Memory Loaded: {detail.session.title}")
        return True

    def _clear_session_pages(self) -> None:
        self.overview_page.set_detail(None)
        self.transcript_page.set_detail(None)
        self.insights_page.set_detail(None)
        self.diagnostics_page.set_detail(None)
        self.graph_page.update_graph_data([], [])
        self.review_page.update_pending_data([])

    def _show_memory_search(self) -> None:
        self.memory_search_page.set_config(self.voice_command_panel.current_transcription_config())
        self.tabs.setCurrentWidget(self.memory_search_page)

    def _ask_selected_session_locally(self, query: str) -> MemoryAskResponse:
        if self._selected_session_id is None:
            return MemoryAskResponse(
                query=query,
                mode="evidence_only",
                answer_type="local_selected_session",
                short_answer="Select a transcribed session first, then ask again.",
                confidence_level="insufficient",
                warnings=["No selected desktop session."],
            )

        detail = self._service.get_session_detail(self._selected_session_id)
        if not detail or not detail.transcripts:
            return MemoryAskResponse(
                query=query,
                mode="evidence_only",
                answer_type="local_selected_session",
                short_answer="No transcript evidence is available for the selected session.",
                confidence_level="insufficient",
                warnings=["Selected session has no transcript."],
            )

        transcript_id = detail.transcripts[-1].id
        analysis = detail.transcript_analyses.get(transcript_id)
        if analysis is None:
            return MemoryAskResponse(
                query=query,
                mode="evidence_only",
                answer_type="local_selected_session",
                short_answer="The selected session has a transcript, but no extracted evidence yet.",
                confidence_level="insufficient",
                warnings=["Selected session has no transcript analysis."],
            )

        evidence_items = self._local_evidence_items(query, detail, transcript_id)
        if not evidence_items:
            return MemoryAskResponse(
                query=query,
                mode="evidence_only",
                answer_type="local_selected_session",
                short_answer="I could not find evidence in the selected session for this question.",
                confidence_level="insufficient",
                warnings=["No selected-session evidence matched the question."],
            )

        chains = [
            EvidenceChain(
                steps=[
                    EvidenceStep(
                        node_id=item["node_id"],
                        node_type=item["node_type"],
                        text=item["text"],
                        source_session_id=str(detail.session.id),
                        source_segment_id=item.get("segment_id"),
                        text_preview=item.get("preview"),
                        start_time=item.get("start"),
                        end_time=item.get("end"),
                    )
                ],
                explanation="Selected desktop session evidence.",
            )
            for item in evidence_items
        ]
        source_segment_ids = [
            str(item["segment_id"])
            for item in evidence_items
            if item.get("segment_id")
        ]
        return MemoryAskResponse(
            query=query,
            mode="evidence_only",
            answer_type="local_selected_session",
            short_answer=self._local_answer_text(evidence_items),
            confidence_level="medium",
            mode_used="desktop_selected_session",
            evidence_chains=chains,
            evidence_coverage_score=1.0,
            source_session_ids=[str(detail.session.id)],
            source_segment_ids=source_segment_ids,
            used_sources=[f"Session {detail.session.id}"],
            warnings=["Answer uses selected desktop-session evidence, including unreviewed extracted items."],
        )

    def _local_evidence_items(
        self,
        query: str,
        detail: SessionDetail,
        transcript_id: int,
    ) -> list[dict[str, object]]:
        analysis = detail.transcript_analyses[transcript_id]
        segment_lookup = {segment.segment_id: segment for segment in analysis.segments}
        categories = self._local_ask_categories(query)
        candidates: list[dict[str, object]] = []

        if "TASK" in categories:
            for index, task in enumerate(analysis.action_items):
                candidates.append(
                    self._local_evidence_item(
                        node_type="TASK",
                        node_id=f"local_task_{transcript_id}_{index}",
                        text=task.title,
                        segment_id=task.source_segment_id,
                        segment_lookup=segment_lookup,
                    )
                )

        if "DECISION" in categories:
            for index, decision in enumerate(analysis.decisions):
                candidates.append(
                    self._local_evidence_item(
                        node_type="DECISION",
                        node_id=f"local_decision_{transcript_id}_{index}",
                        text=decision.decision,
                        segment_id=decision.source_segment_id,
                        segment_lookup=segment_lookup,
                    )
                )

        if "TOPIC" in categories:
            for index, topic in enumerate(analysis.topics):
                candidates.append(
                    {
                        "node_type": "TOPIC",
                        "node_id": f"local_topic_{transcript_id}_{index}",
                        "text": topic.label,
                        "segment_id": None,
                        "preview": topic.label,
                        "start": topic.start,
                        "end": topic.end,
                    }
                )

        if "SEGMENT" in categories:
            for index, segment in enumerate(analysis.segments[:8]):
                text = segment.corrected_text or segment.raw_text
                candidates.append(
                    {
                        "node_type": "SEGMENT",
                        "node_id": f"local_segment_{transcript_id}_{index}",
                        "text": text,
                        "segment_id": segment.segment_id,
                        "preview": text,
                        "start": segment.start,
                        "end": segment.end,
                    }
                )

        candidates = [item for item in candidates if str(item.get("text") or "").strip()]
        if not candidates:
            return []

        terms = self._local_query_terms(query)
        matched = [
            item for item in candidates
            if any(term in self._normalize_local_text(f"{item.get('text', '')} {item.get('preview', '')}") for term in terms)
        ]
        return (matched or candidates)[:8]

    @staticmethod
    def _local_evidence_item(
        *,
        node_type: str,
        node_id: str,
        text: str,
        segment_id: str | None,
        segment_lookup: dict[str, TranscriptAnalysisSegment],
    ) -> dict[str, object]:
        segment = segment_lookup.get(segment_id or "")
        preview = text
        start = None
        end = None
        if segment is not None:
            preview = segment.corrected_text or segment.raw_text or text
            start = segment.start
            end = segment.end
        return {
            "node_type": node_type,
            "node_id": node_id,
            "text": text,
            "segment_id": segment_id,
            "preview": preview,
            "start": start,
            "end": end,
        }

    @classmethod
    def _local_ask_categories(cls, query: str) -> set[str]:
        normalized = cls._normalize_local_text(query)
        categories: set[str] = set()
        if any(token in normalized for token in ("gorev", "task", "action", "yapilacak", "yapacaktik")):
            categories.add("TASK")
        if any(token in normalized for token in ("karar", "decision", "kararlastir")):
            categories.add("DECISION")
        if any(token in normalized for token in ("konu", "topic", "baslik", "hakkinda")):
            categories.add("TOPIC")
        if any(token in normalized for token in ("transkript", "transcript", "soyledi", "bahset")):
            categories.add("SEGMENT")
        return categories or {"TASK", "DECISION", "TOPIC", "SEGMENT"}

    @classmethod
    def _local_query_terms(cls, query: str) -> list[str]:
        stopwords = {
            "about", "adet", "beni", "bana", "bir", "bu", "did", "for", "gorev", "hangi",
            "hakkinda", "ile", "ilgili", "karar", "konu", "nasil", "nedir", "neler", "ne",
            "session", "task", "the", "var", "what", "yapacaktik", "yapilacak",
        }
        words = cls._normalize_local_text(query).replace("?", " ").replace(".", " ").split()
        return [word for word in words if len(word) > 2 and word not in stopwords]

    @staticmethod
    def _normalize_local_text(text: str) -> str:
        translation = str.maketrans({
            "ç": "c", "Ç": "c",
            "ğ": "g", "Ğ": "g",
            "ı": "i", "I": "i", "İ": "i",
            "ö": "o", "Ö": "o",
            "ş": "s", "Ş": "s",
            "ü": "u", "Ü": "u",
        })
        return text.translate(translation).casefold()

    @staticmethod
    def _local_answer_text(evidence_items: list[dict[str, object]]) -> str:
        grouped: dict[str, list[str]] = {"TASK": [], "DECISION": [], "TOPIC": [], "SEGMENT": []}
        for item in evidence_items:
            node_type = str(item.get("node_type") or "")
            text = str(item.get("text") or "").strip()
            if node_type in grouped and text:
                grouped[node_type].append(text)

        parts: list[str] = []
        if grouped["TASK"]:
            parts.append("Tasks: " + "; ".join(grouped["TASK"][:3]))
        if grouped["DECISION"]:
            parts.append("Decisions: " + "; ".join(grouped["DECISION"][:3]))
        if grouped["TOPIC"]:
            parts.append("Topics: " + ", ".join(grouped["TOPIC"][:5]))
        if grouped["SEGMENT"] and not parts:
            parts.append("Transcript evidence: " + "; ".join(grouped["SEGMENT"][:2]))

        answer = "Selected-session evidence found. " + " ".join(parts)
        if len(answer) > 700:
            answer = answer[:697].rstrip() + "..."
        return answer

    def _navigate_to_source(self, session_id_str: str, segment_id: str) -> None:
        session_id = int(session_id_str)
        if session_id != self._selected_session_id:
            if not self._select_session(session_id):
                QMessageBox.warning(self, "Open Source", "The source session could not be found.")
                return
        
        self.tabs.setCurrentWidget(self.transcript_page)
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
        if self._transcription_thread is not None and self._transcription_thread.isRunning():
            QMessageBox.warning(
                self,
                "Transcription in Progress",
                "A local file is still being processed. Wait for it to finish before closing the app.",
            )
            event.ignore()
            return
        if hasattr(self.voice_command_panel, "shutdown"):
            self.voice_command_panel.shutdown()
        super().closeEvent(event)
