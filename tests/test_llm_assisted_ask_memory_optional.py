import pytest
import asyncio
from unittest.mock import MagicMock
from realtime_backend.app.services.evidence_answer_service import EvidenceAnswerService
from realtime_backend.app.services.llm_assisted_ask_service import LLMAssistedAskService
from realtime_backend.app.pipeline.local_llm_provider import LocalLLMEndpointProvider
from realtime_backend.app.config import get_settings
from realtime_backend.app.services.graph_reasoning import GraphReasoningService
from realtime_backend.app.services.graph_repository import ProductionGraphRepository
from realtime_backend.app.database_proxy import DatabaseProxy

@pytest.mark.asyncio
async def test_real_llm_assisted_ask():
    settings = get_settings()
    llm_provider = LocalLLMEndpointProvider(
        base_url=settings.llm_endpoint,
        timeout=10,
        allow_remote=settings.allow_remote_access
    )
    
    if not llm_provider.is_available():
        pytest.skip("Local LLM not available")

    # We need a real reasoning service or a very good mock
    # For this test, let's mock the evidence response to focus on LLM behavior
    from realtime_backend.app.api.memory_models import MemoryAskResponse
    from realtime_backend.app.models import EvidenceChain, EvidenceStep

    evidence = MemoryAskResponse(
        query="FastAPI hakkında ne yapacaktık?",
        mode="llm_assisted",
        answer_type="evidence_only",
        answer_validation_status="accepted",
        short_answer="FastAPI ile ilgili 1 görev bulundu.",
        evidence_chains=[
            EvidenceChain(steps=[
                EvidenceStep(node_id="t1", node_type="task", text="FastAPI endpointini test et")
            ])
        ],
        confidence_level="high",
        source_session_ids=["session_1"]
    )

    service = LLMAssistedAskService(llm_provider)
    response = await service.generate_answer(evidence.query, evidence)
    
    print(f"\nLLM Answer: {response.short_answer}")
    assert response.answer_type == "llm_assisted"
    assert "FastAPI" in response.short_answer
    assert "test" in response.short_answer.lower()
    assert response.confidence_level in ["high", "medium"]

@pytest.mark.asyncio
async def test_llm_hallucination_rejection():
    # Mock LLM provider that returns a hallucinated answer
    mock_llm = MagicMock(spec=LocalLLMEndpointProvider)
    mock_llm.is_available.return_value = True
    # LLM suggests Pytest but evidence doesn't have it
    mock_llm.generate_structured_json.return_value = {
        "answer": "FastAPI endpointini test etmek için Pytest kullanmalısınız.",
        "used_sources": ["1"],
        "confidence": "high"
    }
    
    from realtime_backend.app.api.memory_models import MemoryAskResponse
    from realtime_backend.app.models import EvidenceChain, EvidenceStep

    evidence = MemoryAskResponse(
        query="FastAPI test?",
        mode="llm_assisted",
        answer_type="evidence_only",
        answer_validation_status="accepted",
        short_answer="FastAPI test et.",
        evidence_chains=[
            EvidenceChain(steps=[
                EvidenceStep(node_id="t1", node_type="task", text="FastAPI endpointini test et")
            ])
        ],
        confidence_level="high"
    )

    service = LLMAssistedAskService(mock_llm)
    response = await service.generate_answer(evidence.query, evidence)
    
    assert response.mode_used == "evidence_only_fallback"
    assert "Pytest" in response.rejected_terms
    assert "rejected" in response.warnings[0]
    assert response.short_answer == "FastAPI test et."

@pytest.mark.asyncio
async def test_llm_valid_grounded_answer():
    mock_llm = MagicMock(spec=LocalLLMEndpointProvider)
    mock_llm.is_available.return_value = True
    # LLM stays within evidence
    mock_llm.generate_structured_json.return_value = {
        "answer": "Kayıtlara göre FastAPI endpointi test edilecek.",
        "used_sources": ["1"],
        "confidence": "high"
    }
    
    from realtime_backend.app.api.memory_models import MemoryAskResponse
    from realtime_backend.app.models import EvidenceChain, EvidenceStep

    evidence = MemoryAskResponse(
        query="FastAPI test?",
        mode="llm_assisted",
        answer_type="evidence_only",
        answer_validation_status="accepted",
        short_answer="FastAPI test et.",
        evidence_chains=[
            EvidenceChain(steps=[
                EvidenceStep(node_id="t1", node_type="task", text="FastAPI endpointini test et")
            ])
        ],
        confidence_level="high"
    )

    service = LLMAssistedAskService(mock_llm)
    response = await service.generate_answer(evidence.query, evidence)
    
    assert response.mode_used == "llm_assisted"
    assert not response.rejected_terms
    assert "Kayıtlara göre" in response.short_answer
