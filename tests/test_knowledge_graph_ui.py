import os
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from collective_mindgraph_desktop.ui.pages.knowledge_graph_page import KnowledgeGraphPage

# Ensure offscreen for CI
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

@pytest.fixture
def page(qtbot):
    p = KnowledgeGraphPage()
    qtbot.addWidget(p)
    return p

def test_knowledge_graph_filtering(page, qtbot):
    nodes = [
        {"id": "n1", "type": "TASK", "title": "Task One", "metadata_json": "{}"},
        {"id": "n2", "type": "DECISION", "title": "Decision Two", "metadata_json": "{}"}
    ]
    edges = []
    
    page.update_graph_data(nodes, edges)
    assert page.nodes_table.rowCount() == 2
    
    # Filter by type
    page.type_filter.setCurrentText("TASK")
    assert page.nodes_table.rowCount() == 1
    assert page.nodes_table.item(0, 0).text() == "n1"
    
    # Filter by text
    page.type_filter.setCurrentText("All Types")
    page.search_filter.setText("Two")
    assert page.nodes_table.rowCount() == 1
    assert page.nodes_table.item(0, 0).text() == "n2"

def test_knowledge_graph_selection_shows_detail(page, qtbot):
    nodes = [{"id": "n1", "type": "TASK", "title": "My Task", "metadata_json": '{"priority": "high"}'}]
    page.update_graph_data(nodes, [])
    
    # Select first row
    page.nodes_table.selectRow(0)
    
    detail = page.detail_text.toPlainText()
    assert "Node ID: n1" in detail
    assert "My Task" in detail
    assert '"priority": "high"' in detail
    assert page.edit_button.isEnabled()
    assert page.disable_button.isEnabled()


def test_knowledge_graph_neighbors_use_readable_direction_text(page, qtbot):
    nodes = [
        {"id": "n1", "type": "TASK", "title": "Task One", "metadata_json": "{}"},
        {"id": "n2", "type": "DECISION", "title": "Decision Two", "metadata_json": "{}"},
    ]
    edges = [
        {
            "source_node_id": "n1",
            "target_node_id": "n2",
            "edge_type": "SUPPORTS",
            "confidence": 1.0,
        }
    ]

    page.update_graph_data(nodes, edges)
    page.nodes_table.selectRow(0)

    assert page.neighbors_list.item(0).text() == "OUT [SUPPORTS] to: Decision Two"

def test_knowledge_graph_disabled_node_search_fallback():
    # This tests the reasoning logic in backend
    from realtime_backend.app.services.hybrid_memory_query_service import HybridMemoryQueryService
    from realtime_backend.app.services.memory_graph import GraphNode, NodeType
    from unittest.mock import MagicMock
    import json
    
    mock_repo = MagicMock()
    # Mock SQLite execute for keyword search
    mock_conn = MagicMock()
    # Ensure context manager returns the mock connection
    mock_conn.__enter__.return_value = mock_conn
    mock_repo.database.connect.return_value = mock_conn
    
    # node_0 is active, node_1 is disabled
    def mock_get_node(node_id):
        if node_id == "n0":
            return GraphNode(id="n0", type=NodeType.TASK, properties={"title": "Active"})
        return None
        
    mock_repo.get_node.side_effect = mock_get_node
    
    mock_conn.execute.return_value.fetchall.return_value = [
        {"id": "n0", "type": "TASK", "title": "Active", "text_content": "Active", "metadata_json": '{"disabled": false}'},
        {"id": "n1", "type": "TASK", "title": "Disabled", "text_content": "Disabled", "metadata_json": '{"disabled": true}'}
    ]
    
    service = HybridMemoryQueryService(mock_repo)
    result = service.execute_query("query", use_keyword=True, use_vector=False, use_graph=False)
    
    node_ids = [n.id for n in result.nodes]
    assert "n0" in node_ids
    assert "n1" not in node_ids
