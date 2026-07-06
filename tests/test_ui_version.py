import os
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QStatusBar, QLabel, QTabWidget

# Ensure offscreen for CI
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

def test_rebuilt_ui_is_loaded(qtbot):
    from collective_mindgraph_desktop.ui.main_window import MainWindow
    from collective_mindgraph_desktop.services import CollectiveMindGraphService
    from collective_mindgraph_desktop.ui.pages.session_overview_page import SessionOverviewPage
    from collective_mindgraph_desktop.ui.pages.transcript_page import TranscriptPage
    from collective_mindgraph_desktop.ui.pages.insights_page import InsightsPage
    from collective_mindgraph_desktop.ui.pages.memory_search_page import MemorySearchPage
    from collective_mindgraph_desktop.ui.pages.diagnostics_page import DiagnosticsPage
    
    # We need a service instance
    service = CollectiveMindGraphService()
    window = MainWindow(service)
    qtbot.addWidget(window)
    
    # 1. Check title
    assert "Collective MindGraph" in window.windowTitle()
    assert "Local Technical Memory" in window.windowTitle()
    
    # 2. Check sidebar exists
    assert hasattr(window, "sidebar_container")
    assert window.sidebar_container.objectName() == "Sidebar"
    
    # 3. Check for QTabWidget and Pages
    assert hasattr(window, "tabs")
    assert isinstance(window.tabs, QTabWidget)
    
    # Verify all required pages are in the tabs
    found_pages = []
    for i in range(window.tabs.count()):
        found_pages.append(window.tabs.widget(i).__class__.__name__)
        
    assert "SessionOverviewPage" in found_pages
    assert "TranscriptPage" in found_pages
    assert "InsightsPage" in found_pages
    assert "MemorySearchPage" in found_pages
    assert "DiagnosticsPage" in found_pages
    assert window.memory_search_page._config is not None
    assert window.memory_search_page.ask_panel._config is not None
    
    # 4. Check for Global Search in the sidebar list panel
    assert hasattr(window.session_list_panel, "search_button")
    assert window.session_list_panel.search_button.text() == "Global Memory Search"
    
    # 5. Check for Version Marker in status bar
    status_bar = window.statusBar()
    found_marker = False
    labels = status_bar.findChildren(QLabel)
    for l in labels:
        if "Native MVP" in l.text():
            found_marker = True

    assert found_marker, "Version marker 'Native MVP' not found in status bar"
if __name__ == "__main__":
    pytest.main([__file__])


def test_empty_detail_clears_overview_and_diagnostics(qtbot):
    from collective_mindgraph_desktop.models import (
        Session,
        SessionDetail,
        Transcript,
        TranscriptAnalysis,
        TranscriptAnalysisSegment,
    )
    from collective_mindgraph_desktop.ui.pages.session_overview_page import SessionOverviewPage
    from collective_mindgraph_desktop.ui.pages.diagnostics_page import DiagnosticsPage

    session = Session(
        id=1,
        title="Analyzed Session",
        device_id="DEV",
        status="active",
        created_at="2026-07-06 10:00:00",
        updated_at="2026-07-06 10:00:00",
    )
    transcript = Transcript(id=10, session_id=1, text="Hello", confidence=1.0, created_at=session.created_at)
    analysis = TranscriptAnalysis(
        transcript_id=10,
        source_provider="mock-asr",
        backend_conversation_id="conv",
        raw_text_output="raw",
        corrected_text_output="clean",
        summary="Summary",
        topics=[],
        action_items=[],
        decisions=[],
        people=[],
        speaker_stats=[],
        segments=[
            TranscriptAnalysisSegment(
                segment_id="s1",
                start=0.0,
                end=1.0,
                speaker="Unknown",
                raw_text="raw",
                corrected_text="clean",
                confidence=1.0,
                speaker_confidence=None,
                overlap=False,
                notes=[],
            )
        ],
        quality_report=None,
        created_at=session.created_at,
        updated_at=session.updated_at,
        metadata={"extraction_source": "local_llm", "llm_endpoint": "http://127.0.0.1:1234/v1"},
    )
    detail = SessionDetail(
        session=session,
        transcripts=[transcript],
        graph_nodes=[],
        snapshots=[],
        transcript_analyses={10: analysis},
    )

    overview = SessionOverviewPage()
    diagnostics = DiagnosticsPage()
    qtbot.addWidget(overview)
    qtbot.addWidget(diagnostics)

    overview.set_detail(detail)
    diagnostics.set_detail(detail)
    overview.set_detail(None)
    diagnostics.set_detail(None)

    assert overview.labels["title"].text() == "-"
    assert overview.labels["created"].text() == "-"
    assert overview.pills["segments"].value_label.text() == "0"
    assert diagnostics.labels["llm_endpoint"].text() == "-"
    assert diagnostics.labels["extraction_mode"].text() == "NO_SESSION_ANALYSIS"
    assert diagnostics.labels["raw_length"].text() == "-"


def test_main_window_missing_session_does_not_replace_selection(qtbot, tmp_path):
    from collective_mindgraph_desktop.database import Database
    from collective_mindgraph_desktop.services import CollectiveMindGraphService
    from collective_mindgraph_desktop.ui.main_window import MainWindow

    service = CollectiveMindGraphService(Database(tmp_path / "missing_session.sqlite3"))
    session = service.ingest_transcript("Existing session")
    window = MainWindow(service)
    qtbot.addWidget(window)

    assert window._select_session(session.id)
    assert not window._select_session(9999)

    assert window._selected_session_id == session.id
    assert "not found" in window.statusBar().currentMessage()


def test_main_window_session_filter_uses_sidebar_query(qtbot, tmp_path):
    from collective_mindgraph_desktop.database import Database
    from collective_mindgraph_desktop.services import CollectiveMindGraphService
    from collective_mindgraph_desktop.ui.main_window import MainWindow

    service = CollectiveMindGraphService(Database(tmp_path / "filter_sessions.sqlite3"))
    alpha = service.create_session("Alpha Runtime", "DEV")
    service.create_session("Beta Runtime", "DEV")
    window = MainWindow(service)
    qtbot.addWidget(window)

    window.session_list_panel.set_search_text("Alpha")

    assert window.session_list_panel.list_widget.count() == 1
    assert window.session_list_panel.list_widget.item(0).data(Qt.ItemDataRole.UserRole) == alpha.id


def test_main_window_delete_signal_removes_session_and_clears_detail(qtbot, tmp_path):
    from collective_mindgraph_desktop.database import Database
    from collective_mindgraph_desktop.services import CollectiveMindGraphService
    from collective_mindgraph_desktop.ui.main_window import MainWindow

    service = CollectiveMindGraphService(Database(tmp_path / "delete_session.sqlite3"))
    session = service.ingest_transcript("Delete me from the sidebar.")
    window = MainWindow(service)
    qtbot.addWidget(window)

    assert window._select_session(session.id)
    assert window.overview_page.labels["title"].text() == "Delete me from the sidebar."

    window.session_list_panel.delete_session_requested.emit(session.id)

    assert service.get_session_detail(session.id) is None
    assert window._selected_session_id is None
    assert window.overview_page.labels["title"].text() == "-"
    assert window.transcript_page.table.rowCount() == 0
    assert window.graph_page.nodes_table.rowCount() == 0
    assert not window.graph_page.edit_button.isEnabled()


def test_main_window_close_ignores_active_file_transcription(qtbot, tmp_path, monkeypatch):
    from collective_mindgraph_desktop.database import Database
    from collective_mindgraph_desktop.services import CollectiveMindGraphService
    import collective_mindgraph_desktop.ui.main_window as main_window_module

    class ActiveThread:
        def isRunning(self):
            return True

    warnings: list[str] = []
    monkeypatch.setattr(
        main_window_module.QMessageBox,
        "warning",
        lambda _parent, title, message: warnings.append(f"{title}: {message}"),
    )

    service = CollectiveMindGraphService(Database(tmp_path / "close_guard.sqlite3"))
    window = main_window_module.MainWindow(service)
    qtbot.addWidget(window)
    window._transcription_thread = ActiveThread()
    event = QCloseEvent()

    window.closeEvent(event)

    assert not event.isAccepted()
    assert warnings
    assert "still being processed" in warnings[0]
