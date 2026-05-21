
import pytest
from fastapi.testclient import TestClient
from realtime_backend.app.main import build_app
from unittest.mock import MagicMock

@pytest.fixture
def client():
    app = build_app()
    # Mock reasoning service
    app.state.reasoning_service = MagicMock()
    return TestClient(app)

def test_reason_endpoint_returns_evidence_chains(client):
    # Use real core models for mocking return values
    from collective_mindgraph.core.memory_graph import GraphNode, NodeType
    
    mock_node = GraphNode(id="t1", type=NodeType.TASK, properties={"title": "Mock Task"})
    
    from collective_mindgraph.core.graph_reasoning import ReasoningResult, EvidenceChain, EvidenceStep
    
    mock_chain = EvidenceChain(steps=[EvidenceStep(node=mock_node)])
    client.app.state.reasoning_service.get_intent_based_reasoning.return_value = ReasoningResult(
        chains=[mock_chain]
    )
    
    response = client.get("/reason?q=task")
    assert response.status_code == 200
    data = response.json()
    assert len(data["chains"]) == 1
    assert data["chains"][0]["steps"][0]["text"] == "Mock Task"
