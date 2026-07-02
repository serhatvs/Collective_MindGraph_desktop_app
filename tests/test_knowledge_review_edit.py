
import pytest
import json
from datetime import datetime, UTC
from collective_mindgraph_desktop.database import Database
from collective_mindgraph_desktop.services import CollectiveMindGraphService
from collective_mindgraph_desktop.transcription import TranscriptionResult
from collective_mindgraph.core.memory_graph import NodeType, GraphNode, EdgeType, GraphEdge
from collective_mindgraph.core.source_reference import SourceReference

@pytest.fixture
def service(tmp_path):
    db = Database(tmp_path / "review.sqlite3")
    db.initialize()
    return CollectiveMindGraphService(db)

def test_extraction_lifecycle_starts_as_pending(service):
    # 1. Ingest a mock result
    result = TranscriptionResult(
        conversation_id="c1", model_id="mock", audio_path="a.wav",
        text="FastAPI test.",
        action_items=[{"title": "Test Task", "responsible_person": "Ali", "source_segment_id": "s1"}],
        segments=[{"segment_id": "s1", "corrected_text": "FastAPI test.", "speaker": "Ali"}]
    )
    session = service.ingest_transcription_result(result)
    
    # 2. Check V2 Graph node status
    nodes = service.get_session_graph_data(session.id)["nodes"]
    task_nodes = [n for n in nodes if n["type"] == "TASK"]
    assert len(task_nodes) == 1
    
    meta = json.loads(task_nodes[0]["metadata_json"])
    assert meta["review_status"] == "pending"
    assert meta["original_text"] == "Test Task"

def test_approve_task_changes_status(service):
    repo = service.production_graph
    repo.create_node(GraphNode(
        id="t1", type=NodeType.TASK, 
        properties={"title": "Task", "review_status": "pending"}
    ))
    
    # Update to approved
    service.update_node("t1", {"review_status": "approved"})
    
    node = repo.get_node("t1")
    assert node.properties["review_status"] == "approved"

def test_disabled_task_hidden_from_query():
    from realtime_backend.app.services.hybrid_memory_query_service import HybridMemoryQueryService
    from unittest.mock import MagicMock
    from collective_mindgraph.core.memory_graph import GraphNode, NodeType
    
    mock_repo = MagicMock()
    mock_conn = MagicMock()
    mock_repo.database.connect.return_value = mock_conn
    
    # n1 is disabled
    node1 = GraphNode(id="n1", type=NodeType.TASK, properties={"disabled": True})
    mock_repo.get_node.return_value = node1
    
    mock_conn.execute.return_value.fetchall.return_value = [
        {"id": "n1", "type": "TASK", "title": "Disabled", "text_content": "Disabled", "metadata_json": '{"disabled": true}'}
    ]
    
    service = HybridMemoryQueryService(mock_repo)
    result = service.execute_query("query")
    assert len(result.nodes) == 0

def test_rejected_task_hidden_from_query():
    from realtime_backend.app.services.hybrid_memory_query_service import HybridMemoryQueryService
    from unittest.mock import MagicMock
    from collective_mindgraph.core.memory_graph import GraphNode, NodeType
    
    mock_repo = MagicMock()
    mock_conn = MagicMock()
    mock_repo.database.connect.return_value = mock_conn
    
    # n1 is rejected
    node1 = GraphNode(id="n1", type=NodeType.TASK, properties={"review_status": "rejected"})
    mock_repo.get_node.return_value = node1
    
    mock_conn.execute.return_value.fetchall.return_value = [
        {"id": "n1", "type": "TASK", "title": "Rejected", "text_content": "Rejected", "metadata_json": '{"review_status": "rejected"}'}
    ]
    
    service = HybridMemoryQueryService(mock_repo)
    result = service.execute_query("query")
    assert len(result.nodes) == 0

def test_export_import_preserves_review_metadata(service, tmp_path):
    session = service.create_session("Export Review", "DEV")
    service.production_graph.create_node(GraphNode(
        id="t1", type=NodeType.TASK, 
        properties={"title": "Reviewed", "review_status": "approved", "original_text": "Raw"},
        source=SourceReference(session_id=str(session.id))
    ))
    
    path = tmp_path / "review_export.json"
    service.export_session(session.id, path)
    
    # Import into new DB
    db2 = Database(tmp_path / "imported_review.sqlite3")
    db2.initialize()
    service2 = CollectiveMindGraphService(db2)
    imported = service2.import_session(path)
    
    nodes = service2.get_session_graph_data(imported.id)["nodes"]
    task = [n for n in nodes if n["type"] == "TASK"][0]
    
    meta = json.loads(task["metadata_json"])
    assert meta["review_status"] == "approved"
    assert meta["original_text"] == "Raw"

def test_graph_traversal_preserves_source_after_edit(service):
    repo = service.production_graph
    source = SourceReference(session_id="s1", segment_id="seg1")
    repo.create_node(GraphNode(
        id="n1", type=NodeType.TASK, 
        properties={"title": "Old"},
        source=source
    ))
    
    # Edit
    service.update_node("n1", {"title": "New", "edited_by_user": True})
    
    # Check
    node = repo.get_node("n1")
    assert node.properties["title"] == "New"
    assert node.source.session_id == "s1"
    assert node.source.segment_id == "seg1"

def test_extended_node_review_lifecycle_updates_status_and_disable_flags(service):
    repo = service.production_graph
    repo.create_node(GraphNode(
        id="risk1",
        type=NodeType.RISK,
        properties={"title": "Deployment risk", "review_status": "pending"},
        source=SourceReference(session_id="s1", segment_id="seg1"),
    ))

    assert service.update_node("risk1", {"review_status": "approved"})
    node = repo.get_node("risk1")
    assert node.properties["review_status"] == "approved"

    assert service.update_node("risk1", {"title": "Updated deployment risk", "review_status": "edited"})
    node = repo.get_node("risk1")
    assert node.properties["title"] == "Updated deployment risk"
    assert node.properties["review_status"] == "edited"

    assert service.update_node("risk1", {"review_status": "rejected", "disabled": True, "disabled_reason": "duplicate"})
    node = repo.get_node("risk1")
    assert node.properties["review_status"] == "rejected"
    assert node.properties["disabled"] is True
    assert node.properties["disabled_reason"] == "duplicate"

def test_merge_nodes_marks_source_and_records_target_metadata(service):
    repo = service.production_graph
    source_ref = SourceReference(session_id="s1", segment_id="seg1")
    target_ref = SourceReference(session_id="s1", segment_id="seg2")
    repo.create_node(GraphNode(
        id="risk_source",
        type=NodeType.RISK,
        properties={"title": "Deployment may fail", "review_status": "pending"},
        source=source_ref,
    ))
    repo.create_node(GraphNode(
        id="risk_target",
        type=NodeType.RISK,
        properties={"title": "Deployment risk", "review_status": "approved"},
        source=target_ref,
    ))

    assert service.merge_nodes("risk_source", "risk_target")

    source = repo.get_node("risk_source")
    target = repo.get_node("risk_target")
    assert source.properties["review_status"] == "merged"
    assert source.properties["merged_into_node_id"] == "risk_target"
    assert source.source.session_id == "s1"
    assert source.source.segment_id == "seg1"
    assert target.properties["review_status"] == "approved"
    assert target.properties["merged_source_node_ids"] == ["risk_source"]
    assert target.source.segment_id == "seg2"

    merge_edges = [
        edge for edge in repo.get_edges_by_node("risk_source", as_source=True)
        if edge.type == EdgeType.NODE_MERGED_INTO
    ]
    assert len(merge_edges) == 1
    assert merge_edges[0].target_node_id == "risk_target"

def test_merge_nodes_fails_safely_for_missing_or_incompatible_nodes(service):
    repo = service.production_graph
    repo.create_node(GraphNode(id="task1", type=NodeType.TASK, properties={"title": "Task"}))
    repo.create_node(GraphNode(id="risk1", type=NodeType.RISK, properties={"title": "Risk"}))

    assert service.merge_nodes("missing", "task1") is False
    assert service.merge_nodes("task1", "missing") is False
    assert service.merge_nodes("task1", "task1") is False
    assert service.merge_nodes("task1", "risk1") is False

def test_merged_source_hidden_from_backend_hybrid_query():
    from realtime_backend.app.services.hybrid_memory_query_service import HybridMemoryQueryService
    from unittest.mock import MagicMock
    from realtime_backend.app.services.memory_graph import GraphNode as BackendGraphNode, NodeType as BackendNodeType

    mock_repo = MagicMock()
    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_repo.database.connect.return_value = mock_conn
    mock_repo.get_node.return_value = BackendGraphNode(
        id="merged1",
        type=BackendNodeType.TASK,
        properties={"title": "Merged task", "review_status": "merged"},
    )
    mock_conn.execute.return_value.fetchall.return_value = [
        {"id": "merged1", "type": "TASK", "title": "Merged task", "text_content": "Merged task", "metadata_json": '{"review_status": "merged"}'}
    ]

    result = HybridMemoryQueryService(mock_repo).execute_query("Merged", use_keyword=True, use_vector=False, use_graph=False)

    assert result.nodes == []
