import pytest

from collective_mindgraph.core.ai_provider import LocalLLMProvider, LocalEmbeddingProvider
from collective_mindgraph.core.memory_graph import GraphNode, GraphEdge, NodeType, EdgeType
from collective_mindgraph.core.source_reference import SourceReference
from collective_mindgraph.core.hybrid_query import HybridQueryResult, HybridQueryInterface

def test_source_reference_instantiation():
    ref = SourceReference(
        session_id="session_123",
        segment_id="seg_456",
        timestamp_start=1.5,
        timestamp_end=5.0,
        extractor_model="test_llm"
    )
    assert ref.session_id == "session_123"
    assert ref.confidence == 1.0

def test_memory_graph_node_and_edge():
    node_session = GraphNode(
        id="node_1",
        type=NodeType.SESSION,
        properties={"title": "Test Session"}
    )
    
    node_task = GraphNode(
        id="node_2",
        type=NodeType.TASK,
        properties={"title": "Fix the pipeline"},
        source=SourceReference(session_id="node_1")
    )
    
    assert node_session.type == NodeType.SESSION
    assert node_task.type == NodeType.TASK
    
    edge = GraphEdge(
        id="edge_1",
        source_node_id="node_1",
        target_node_id="node_2",
        type=EdgeType.SEGMENT_CREATES_TASK
    )
    
    assert edge.type == EdgeType.SEGMENT_CREATES_TASK

def test_hybrid_query_result():
    result = HybridQueryResult(
        nodes=[GraphNode(id="test", type=NodeType.DOCUMENT)],
        generated_answer="The pipeline needs fixing.",
        confidence=0.95
    )
    
    assert len(result.nodes) == 1
    assert result.generated_answer == "The pipeline needs fixing."
    assert result.confidence == 0.95
