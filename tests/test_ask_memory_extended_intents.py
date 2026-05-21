import pytest
from unittest.mock import MagicMock
from realtime_backend.app.services.evidence_answer_service import EvidenceAnswerService
from realtime_backend.app.services.graph_reasoning import GraphReasoningService, ReasoningResult, EvidenceChain, EvidenceStep
from realtime_backend.app.services.memory_graph import GraphNode, NodeType

@pytest.fixture
def mock_reasoning_service():
    service = MagicMock(spec=GraphReasoningService)
    return service

def test_ask_memory_extended_intents_risk(mock_reasoning_service):
    node = GraphNode(id="r1", type=NodeType.RISK, properties={"title": "Data loss", "review_status": "completed"})
    chain = EvidenceChain(steps=[EvidenceStep(node=node)])
    mock_reasoning_service.get_intent_based_reasoning.return_value = ReasoningResult(chains=[chain])
    
    service = EvidenceAnswerService(mock_reasoning_service)
    response = service.ask("Riskler neler?")
    
    assert response.answer_type == "evidence_only"
    assert "risk" in response.short_answer.lower()
    assert response.evidence_chains[0].steps[0].node_id == "r1"

def test_ask_memory_extended_intents_open_question(mock_reasoning_service):
    node = GraphNode(id="oq1", type=NodeType.OPEN_QUESTION, properties={"title": "Deployment?", "review_status": "completed"})
    chain = EvidenceChain(steps=[EvidenceStep(node=node)])
    mock_reasoning_service.get_intent_based_reasoning.return_value = ReasoningResult(chains=[chain])
    
    service = EvidenceAnswerService(mock_reasoning_service)
    response = service.ask("Açık sorular neler?")
    
    assert "açık soru" in response.short_answer.lower()
    assert response.evidence_chains[0].steps[0].node_id == "oq1"

def test_ask_memory_extended_intents_follow_up(mock_reasoning_service):
    node = GraphNode(id="fu1", type=NodeType.FOLLOW_UP, properties={"title": "Check logs", "review_status": "completed"})
    chain = EvidenceChain(steps=[EvidenceStep(node=node)])
    mock_reasoning_service.get_intent_based_reasoning.return_value = ReasoningResult(chains=[chain])
    
    service = EvidenceAnswerService(mock_reasoning_service)
    response = service.ask("Follow-up maddeleri neler?")
    
    assert "follow-up" in response.short_answer.lower()
    assert response.evidence_chains[0].steps[0].node_id == "fu1"

def test_ask_memory_extended_intents_entity(mock_reasoning_service):
    node = GraphNode(id="e1", type=NodeType.ENTITY, properties={"title": "Docker", "review_status": "completed"})
    chain = EvidenceChain(steps=[EvidenceStep(node=node)])
    mock_reasoning_service.get_intent_based_reasoning.return_value = ReasoningResult(chains=[chain])
    
    service = EvidenceAnswerService(mock_reasoning_service)
    response = service.ask("Hangi tool kullanıldı?")
    
    assert "entity" in response.short_answer.lower()
    assert response.evidence_chains[0].steps[0].node_id == "e1"
