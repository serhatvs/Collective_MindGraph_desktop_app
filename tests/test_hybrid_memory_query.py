import pytest
import sqlite3
from collective_mindgraph_desktop.database import Database
from collective_mindgraph.infrastructure.database.graph_repository import ProductionGraphRepository
from collective_mindgraph.infrastructure.database.vector_repository import VectorRepository
from collective_mindgraph.infrastructure.ai.local_embedding_provider import MockLocalEmbeddingProvider
from collective_mindgraph.reasoning.hybrid_memory_query_service import HybridMemoryQueryService
from collective_mindgraph.core.memory_graph import GraphNode, GraphEdge, NodeType, EdgeType
from collective_mindgraph.core.source_reference import SourceReference

@pytest.fixture
def setup():
    db = Database(None) # Use in-memory if possible, but Database uses path.
    # We'll use a temp file for setup
    pass

def test_hybrid_query_merges_and_expands(tmp_path):
    db_path = tmp_path / "hybrid.sqlite3"
    db = Database(db_path)
    db.initialize()
    conn = db.connect()
    
    graph_repo = ProductionGraphRepository(db)
    vector_repo = VectorRepository(db, expected_dim=4)
    provider = MockLocalEmbeddingProvider(dim=4)
    
    # 1. Create a SEGMENT node that mentions "FastAPI"
    seg_node = GraphNode(
        id="seg_1", 
        type=NodeType.SEGMENT, 
        properties={"text": "Let's discuss FastAPI today."},
        source=SourceReference(session_id="session_1", segment_id="s1")
    )
    graph_repo.create_node(seg_node)
    vector_repo.store_embedding("seg_1", "SEGMENT", "FastAPI today", provider.embed_text("FastAPI today"))
    
    # 2. Create a TASK node linked to that segment
    task_node = GraphNode(
        id="task_1", 
        type=NodeType.TASK, 
        properties={"title": "Fix FastAPI bug"},
        source=SourceReference(session_id="session_1", segment_id="s1")
    )
    graph_repo.create_node(task_node)
    graph_repo.create_edge(GraphEdge(
        id="e1", 
        source_node_id="seg_1", 
        target_node_id="task_1", 
        type=EdgeType.SEGMENT_CREATES_TASK
    ))

    service = HybridMemoryQueryService(graph_repo, vector_repo, provider)
    
    # Query for "FastAPI"
    # Should match segment via vector/keyword and expand to task via graph
    result = service.execute_query("FastAPI", use_keyword=True, use_vector=True, use_graph=True)
    
    node_ids = [n.id for n in result.nodes]
    assert "seg_1" in node_ids
    assert "task_1" in node_ids
    
    # Verify metadata richness
    seg_res = [n for n in result.nodes if n.id == "seg_1"][0]
    assert "matched_by" in seg_res.properties
    assert "vector" in seg_res.properties["matched_by"]
    
    task_res = [n for n in result.nodes if n.id == "task_1"][0]
    assert "graph" in task_res.properties["matched_by"]
    assert "SEGMENT --(SEGMENT_CREATES_TASK)--> TASK" in task_res.properties["edge_path"]
