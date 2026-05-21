import os
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from collective_mindgraph_desktop.transcription import (
    QueryResultItem,
    QueryResponse,
    RealtimeBackendTranscriptionConfig,
)
from collective_mindgraph_desktop.ui.pages.memory_search_page import MemorySearchPage
from collective_mindgraph_desktop.ui.components.result_card import ResultCard

# Set offscreen platform for CI
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

def test_memory_search_page_displays_results(qtbot):
    page = MemorySearchPage()
    qtbot.addWidget(page)
    
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
    
    page._handle_query_finished(response)
    
    assert page.results_list.count() == 1
    item = page.results_list.item(0)
    
    # Since we use setItemWidget, we need to check the widget
    card = page.results_list.itemWidget(item)
    assert isinstance(card, ResultCard)
    assert card.type_badge.text() == "TASK"
    assert "FastAPI" in card.title_label.text()
    assert "Relevance: 1.10" in card.meta_label.text()
    assert "Memory: conv_1" in card.meta_label.text()

def test_memory_search_page_emits_navigation_signal(qtbot):
    page = MemorySearchPage()
    qtbot.addWidget(page)
    
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
    page._handle_query_finished(response)
    
    # Track signal
    with qtbot.waitSignal(page.source_navigation_requested) as blocker:
        # Simulate double click
        page.results_list.itemDoubleClicked.emit(page.results_list.item(0))
        
    assert blocker.args == ["conv_2", "s2"]

if __name__ == "__main__":
    pytest.main([__file__])
