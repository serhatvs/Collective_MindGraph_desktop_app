import os
import pytest
from PySide6.QtWidgets import QApplication, QComboBox
from collective_mindgraph_desktop.ui.pages.memory_search_page import MemorySearchPage
from collective_mindgraph_desktop.transcription import RealtimeBackendTranscriptionConfig

# Ensure offscreen for CI
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

def test_memory_search_ui_mode_selector(qtbot):
    page = MemorySearchPage()
    qtbot.addWidget(page)
    
    # 1. Check if mode selector exists
    assert hasattr(page, "mode_selector")
    assert isinstance(page, MemorySearchPage)
    
    selector = page.mode_selector
    assert selector.count() == 3
    assert selector.itemText(0) == "Hybrid"
    assert selector.itemText(1) == "Semantic"
    assert selector.itemText(2) == "Keyword"
    
    # 2. Check default mode
    assert selector.currentText() == "Hybrid"

def test_memory_search_ui_query_pass_mode(qtbot):
    page = MemorySearchPage()
    page.set_config(RealtimeBackendTranscriptionConfig())
    qtbot.addWidget(page)
    
    page.search_input.setText("test query")
    page.mode_selector.setCurrentText("Semantic")
    
    # Trigger search
    page.search_button.click()
    
    # Wait for thread to start or work to be assigned
    assert page._query_worker._mode == "semantic"
    
    # Cleanup thread to avoid fatal error
    if page._query_thread:
        page._query_thread.quit()
        page._query_thread.wait()
