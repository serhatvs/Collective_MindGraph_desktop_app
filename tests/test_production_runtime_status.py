
import os
import pytest
from unittest.mock import patch, MagicMock

from realtime_backend.app.pipeline.extraction import AIExtractionService
from realtime_backend.app.models import ConversationTranscript, TranscriptSegment
from realtime_backend.app.config import get_settings

def test_extraction_service_reports_fallback_on_unreachable_llm():
    settings = get_settings()
    # Mock LLM provider to be unreachable
    with patch("realtime_backend.app.pipeline.local_llm_provider.LocalLLMEndpointProvider.is_available", return_value=False):
        service = AIExtractionService(settings)
        
        transcript = ConversationTranscript(
            conversation_id="test", source="test", segments=[TranscriptSegment(segment_id="s1", start=0, end=1, speaker="S", corrected_text="test")]
        )
        
        import asyncio
        result = asyncio.run(service.extract_intelligence(transcript))
        
        assert result.metadata["extraction_source"] == "heuristic_fallback"
        assert "not reachable" in result.metadata["extraction_fallback_reason"]

def test_extraction_service_reports_llm_success():
    settings = get_settings()
    with patch("realtime_backend.app.pipeline.local_llm_provider.LocalLLMEndpointProvider.is_available", return_value=True):
        with patch("realtime_backend.app.pipeline.local_llm_provider.LocalLLMEndpointProvider.generate_structured_json", return_value={"summary": "LLM Sum", "tasks": [], "decisions": [], "topics": []}):
            service = AIExtractionService(settings)
            
            transcript = ConversationTranscript(
                conversation_id="test", source="test", segments=[TranscriptSegment(segment_id="s1", start=0, end=1, speaker="S", corrected_text="test")]
            )
            
            import asyncio
            result = asyncio.run(service.extract_intelligence(transcript))
            
            assert result.metadata["extraction_source"] == "local_llm"
            assert result.summary == "LLM Sum"

def test_query_endpoint_mode_handling():
    # This would ideally be an integration test with the running backend
    # For now we can test the HybridMemoryQueryService logic directly
    pass
