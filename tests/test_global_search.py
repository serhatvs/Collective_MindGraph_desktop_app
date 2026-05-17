import os
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from collective_mindgraph_desktop.transcription import (
    QueryResultItem,
    QueryResponse,
    RealtimeBackendTranscriptionConfig,
)
from collective_mindgraph_desktop.ui.memory_search_panel import MemorySearchPanel

# Set offscreen platform for CI
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

def test_memory_search_panel_displays_results(qtbot):
    panel = MemorySearchPanel()
    qtbot.addWidget(panel)
    
    # Mock response
    response = QueryResponse(
        query="FastAPI",
        results=[
            QueryResultItem(
                result_type="task",
                text="Test FastAPI endpoint",
                source_session_id="conv_1",
                source_segment_id="s1",
                matched_field="title",
                matched_terms=["fastapi"],
                score=1.1,
                preview="...test the FastAPI endpoint..."
            )
        ]
    )
    
    panel._handle_query_finished(response)
    
    assert panel.results_list.count() == 1
    item = panel.results_list.item(0)
    assert "[TASK]" in item.text()
    assert "FastAPI" in item.text()
    assert "Score: 1.10" in item.text()
    assert "Session: conv_1" in item.text()

def test_memory_search_panel_emits_navigation_signal(qtbot):
    panel = MemorySearchPanel()
    qtbot.addWidget(panel)
    
    response = QueryResponse(
        query="SQLite",
        results=[
            QueryResultItem(
                result_type="decision",
                text="Use SQLite for storage",
                source_session_id="conv_2",
                source_segment_id="s2",
                matched_field="decision"
            )
        ]
    )
    panel._handle_query_finished(response)
    
    # Track signal
    with qtbot.waitSignal(panel.source_navigation_requested) as blocker:
        # Simulate double click
        panel.results_list.itemDoubleClicked.emit(panel.results_list.item(0))
        
    assert blocker.args == ["conv_2", "s2"]

if __name__ == "__main__":
    pytest.main([__file__])
