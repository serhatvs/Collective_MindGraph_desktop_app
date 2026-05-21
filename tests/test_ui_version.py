import os
import pytest
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
    assert "Collective MindGraph — Local Technical Memory" in window.windowTitle()
    
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
