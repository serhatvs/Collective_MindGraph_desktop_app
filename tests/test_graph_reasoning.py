
import pytest
from unittest.mock import MagicMock
from collective_mindgraph.core.graph_reasoning import GraphReasoningService, EvidenceChain, EvidenceStep
from collective_mindgraph.core.memory_graph import GraphNode, GraphEdge, NodeType, EdgeType

def test_find_related_items_traversal():
    mock_repo = MagicMock()
    
    # 1. Setup Graph: Topic -> Segment -> Task
    topic = GraphNode(id="topic1", type=NodeType.TOPIC, properties={"title": "FastAPI"})
    segment = GraphNode(id="seg1", type=NodeType.SEGMENT, properties={"text": "Let's test FastAPI."})
    task = GraphNode(id="task1", type=NodeType.TASK, properties={"title": "Test Task", "review_status": "approved"})
    
    mock_repo.find_nodes_by_type.return_value = [topic]
    
    # Mock neighbors
    e1 = GraphEdge(id="e1", source_node_id="seg1", target_node_id="topic1", type=EdgeType.SEGMENT_MENTIONS_TOPIC)
    mock_repo.get_neighbors.side_effect = [
        [(e1, segment)], # direction='in' for topic
        [(GraphEdge(id="e2", source_node_id="seg1", target_node_id="task1", type=EdgeType.SEGMENT_CREATES_TASK), task)] # direction='out' for segment
    ]
    
    service = GraphReasoningService(mock_repo)
    result = service.find_related_items("FastAPI", NodeType.TASK)
    
    assert len(result.chains) == 1
    chain = result.chains[0]
    assert chain.steps[0].node.id == "topic1"
    assert chain.steps[1].node.id == "seg1"
    assert chain.steps[2].node.id == "task1"

def test_reasoning_respects_review_status():
    mock_repo = MagicMock()
    topic = GraphNode(id="topic1", type=NodeType.TOPIC, properties={"title": "FastAPI"})
    segment = GraphNode(id="seg1", type=NodeType.SEGMENT, properties={"text": "..."})
    rejected_task = GraphNode(id="task1", type=NodeType.TASK, properties={"title": "Reject", "review_status": "rejected"})
    
    mock_repo.find_nodes_by_type.return_value = [topic]
    e1 = GraphEdge(id="e1", source_node_id="seg1", target_node_id="topic1", type=EdgeType.SEGMENT_MENTIONS_TOPIC)
    e2 = GraphEdge(id="e2", source_node_id="seg1", target_node_id="task1", type=EdgeType.SEGMENT_CREATES_TASK)
    
    mock_repo.get_neighbors.side_effect = [
        [(e1, segment)],
        [(e2, rejected_task)]
    ]
    
    service = GraphReasoningService(mock_repo)
    result = service.find_related_items("FastAPI", NodeType.TASK)
    
    # Should be empty because task is rejected
    assert len(result.chains) == 0

def test_intent_parsing_logic():
    mock_repo = MagicMock()
    service = GraphReasoningService(mock_repo)
    
    # Mock find_nodes_by_type for task search
    mock_repo.find_nodes_by_type.return_value = []
    
    # Test task intent - should return ReasoningResult with warnings but no crash
    result = service.get_intent_based_reasoning("FastAPI ile ilgili görevler")
    assert isinstance(result.warnings, list)
    assert any("No topic found" in w for w in result.warnings)
