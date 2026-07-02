import pytest
from unittest.mock import MagicMock
from realtime_backend.app.services.evidence_answer_service import EvidenceAnswerService
from realtime_backend.app.services.graph_reasoning import GraphReasoningService, ReasoningResult, EvidenceChain, EvidenceStep
from realtime_backend.app.services.memory_graph import GraphNode, NodeType
from realtime_backend.app.services.source_reference import SourceReference

@pytest.fixture
def mock_reasoning_service():
    service = MagicMock(spec=GraphReasoningService)
    return service

def test_ask_görev_intent(mock_reasoning_service):
    # Setup mock data
    node = GraphNode(id="t1", type=NodeType.TASK, properties={"title": "FastAPI test et", "review_status": "completed"})
    chain = EvidenceChain(steps=[EvidenceStep(node=node)])
    mock_reasoning_service.get_intent_based_reasoning.return_value = ReasoningResult(chains=[chain])
    
    service = EvidenceAnswerService(mock_reasoning_service)
    response = service.ask("FastAPI ile ilgili görevler ne?")
    
    assert response.answer_type == "evidence_only"
    assert "FastAPI" in response.short_answer
    assert "1 adet görev" in response.short_answer
    assert len(response.evidence_chains) == 1
    assert response.evidence_chains[0].steps[0].node_id == "t1"

def test_ask_evidence_step_includes_exact_source_metadata(mock_reasoning_service):
    node = GraphNode(
        id="task_1",
        type=NodeType.TASK,
        properties={"title": "Send the launch checklist", "review_status": "completed"},
        source=SourceReference(
            session_id="session_7",
            segment_id="s1",
            timestamp_start=12.5,
            timestamp_end=18.75,
            text_preview="Clean segment text",
            id="source_ref_1",
        ),
    )
    chain = EvidenceChain(steps=[EvidenceStep(node=node)])
    mock_reasoning_service.get_intent_based_reasoning.return_value = ReasoningResult(chains=[chain])

    service = EvidenceAnswerService(mock_reasoning_service)
    response = service.ask("launch task?")
    step = response.evidence_chains[0].steps[0]

    assert step.source_reference_id == "source_ref_1"
    assert step.source_session_id == "session_7"
    assert step.source_segment_id == "s1"
    assert step.text_preview == "Clean segment text"
    assert step.start_time == 12.5
    assert step.end_time == 18.75

def test_ask_no_evidence(mock_reasoning_service):
    mock_reasoning_service.get_intent_based_reasoning.return_value = ReasoningResult(chains=[])
    
    service = EvidenceAnswerService(mock_reasoning_service)
    response = service.ask("Bilinmeyen bir konu?")
    
    assert response.confidence_level == "insufficient"
    assert "bulamadım" in response.short_answer

def test_ask_pending_filtering(mock_reasoning_service):
    node = GraphNode(id="t1", type=NodeType.TASK, properties={"title": "Pending Task", "review_status": "pending"})
    chain = EvidenceChain(steps=[EvidenceStep(node=node)])
    mock_reasoning_service.get_intent_based_reasoning.return_value = ReasoningResult(chains=[chain])
    
    service = EvidenceAnswerService(mock_reasoning_service)
    
    # Should be excluded by default
    response = service.ask("Görevler?", include_pending=False)
    assert len(response.evidence_chains) == 0
    
    # Should be included if requested
    response = service.ask("Görevler?", include_pending=True)
    assert len(response.evidence_chains) == 1
