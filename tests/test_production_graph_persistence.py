import os
import pytest
from pathlib import Path

from collective_mindgraph_desktop.database import Database
from collective_mindgraph.infrastructure.database.graph_repository import ProductionGraphRepository
from collective_mindgraph.core.memory_graph import GraphNode, GraphEdge, NodeType, EdgeType
from collective_mindgraph.core.source_reference import SourceReference

@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "test_v2_graph.sqlite3"
    db = Database(db_path)
    db.initialize()
    return ProductionGraphRepository(db)

def test_create_and_get_node(repo):
    source = SourceReference(session_id="session_1")
    node = GraphNode(id="node_1", type=NodeType.SESSION, properties={"title": "Test"}, source=source)
    
    repo.create_node(node)
    
    fetched = repo.get_node("node_1")
    assert fetched is not None
    assert fetched.type == NodeType.SESSION
    assert fetched.properties["title"] == "Test"
    assert fetched.source.session_id == "session_1"

def test_create_and_get_edges(repo):
    node1 = GraphNode(id="node_1", type=NodeType.SESSION, properties={"title": "Session"})
    node2 = GraphNode(id="node_2", type=NodeType.SEGMENT, properties={"text": "Hello"})
    repo.create_node(node1)
    repo.create_node(node2)
    
    edge = GraphEdge(
        id="edge_1", 
        source_node_id="node_1", 
        target_node_id="node_2", 
        type=EdgeType.SESSION_HAS_SEGMENT
    )
    repo.create_edge(edge)
    
    edges_from_n1 = repo.get_edges_by_node("node_1", as_source=True)
    assert len(edges_from_n1) == 1
    assert edges_from_n1[0].target_node_id == "node_2"
    
    edges_to_n2 = repo.get_edges_by_node("node_2", as_source=False)
    assert len(edges_to_n2) == 1
    assert edges_to_n2[0].source_node_id == "node_1"

def test_find_nodes_by_type(repo):
    repo.create_node(GraphNode(id="n1", type=NodeType.TASK, properties={"title": "Task 1"}))
    repo.create_node(GraphNode(id="n2", type=NodeType.TASK, properties={"title": "Task 2"}))
    repo.create_node(GraphNode(id="n3", type=NodeType.DECISION, properties={"title": "Dec 1"}))
    
    tasks = repo.find_nodes_by_type(NodeType.TASK)
    assert len(tasks) == 2
    
    decisions = repo.find_nodes_by_type(NodeType.DECISION)
    assert len(decisions) == 1

def test_delete_graph_data_for_session(repo):
    source = SourceReference(session_id="session_to_delete")
    repo.create_node(GraphNode(id="n1", type=NodeType.SESSION, source=source))
    repo.create_node(GraphNode(id="n2", type=NodeType.SEGMENT, source=source))
    
    repo.create_edge(GraphEdge(
        id="e1", 
        source_node_id="n1", 
        target_node_id="n2", 
        type=EdgeType.SESSION_HAS_SEGMENT,
        source=source
    ))
    
    assert repo.get_node("n1") is not None
    assert len(repo.get_edges_by_node("n1")) == 1
    
    repo.delete_graph_data_for_session("session_to_delete")
    
    assert repo.get_node("n1") is None
    assert repo.get_node("n2") is None
    assert len(repo.get_edges_by_node("n1")) == 0
