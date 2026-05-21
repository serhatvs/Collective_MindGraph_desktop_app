import pytest
from collective_mindgraph.core.memory_graph import NodeType, EdgeType

def test_extended_node_types_exist():
    assert hasattr(NodeType, "ENTITY")
    assert hasattr(NodeType, "RISK")
    assert hasattr(NodeType, "OPEN_QUESTION")
    assert hasattr(NodeType, "FOLLOW_UP")
    
    assert NodeType.ENTITY.value == "ENTITY"
    assert NodeType.RISK.value == "RISK"
    assert NodeType.OPEN_QUESTION.value == "OPEN_QUESTION"
    assert NodeType.FOLLOW_UP.value == "FOLLOW_UP"

def test_extended_edge_types_exist():
    assert hasattr(EdgeType, "SEGMENT_MENTIONS_ENTITY")
    assert hasattr(EdgeType, "SEGMENT_RAISES_RISK")
    assert hasattr(EdgeType, "SEGMENT_RAISES_OPEN_QUESTION")
    assert hasattr(EdgeType, "SEGMENT_CREATES_FOLLOW_UP")
    assert hasattr(EdgeType, "RISK_RELATED_TO_TOPIC")
    assert hasattr(EdgeType, "OPEN_QUESTION_RELATED_TO_TOPIC")
    assert hasattr(EdgeType, "FOLLOW_UP_RELATED_TO_TASK")
    assert hasattr(EdgeType, "ENTITY_RELATED_TO_TOPIC")
