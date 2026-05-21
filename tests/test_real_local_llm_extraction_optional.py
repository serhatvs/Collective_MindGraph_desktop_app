
import os
import pytest
import asyncio
import json
from pathlib import Path

# Add src and backend to path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from realtime_backend.app.pipeline.extraction import AIExtractionService
from realtime_backend.app.models import ConversationTranscript, TranscriptSegment
from realtime_backend.app.config import get_settings

def test_real_local_llm_extraction():
    settings = get_settings()
    service = AIExtractionService(settings)
    
    # Check if local LLM is available before running
    is_available = False
    try:
        is_available = service.llm_provider.is_available()
    except Exception:
        pass
        
    if not is_available:
        pytest.skip(f"Real local LLM server not reachable at {service.llm_provider.base_url}. Skipping optional extraction test.")

    # Technical Turkish transcript for real LLM testing
    transcript = ConversationTranscript(
        conversation_id="real_llm_test",
        source="verification_script",
        segments=[
            TranscriptSegment(
                segment_id="s1", start=0, end=10, speaker="Serhat",
                corrected_text="Bu hafta FastAPI endpointini test edeceğiz."
            ),
            TranscriptSegment(
                segment_id="s2", start=10, end=20, speaker="Ali",
                corrected_text="SQLite kayıtlarında raw transcript ve cleaned transcript ayrı tutulacak."
            ),
            TranscriptSegment(
                segment_id="s3", start=20, end=30, speaker="Veli",
                corrected_text="VAD ayarlarını kontrol etmemiz gerekiyor."
            )
        ]
    )

    # Run real LLM extraction
    result = asyncio.run(service.extract_intelligence(transcript))

    print(f"\nExtraction Source: {result.metadata.get('extraction_source')}")
    assert result.metadata.get("extraction_source") == "local_llm"
    assert result.metadata.get("json_valid") is True
    
    # Verify content richness
    full_extracted_text = (
        " ".join([t.title for t in result.action_items]) + 
        " ".join([d.decision for d in result.decisions]) +
        " ".join([t.label for t in result.topics]) +
        " ".join(result.metadata.get("entities", []))
    ).lower()
    
    print(f"Extracted Text Pool: {full_extracted_text}")
    
    # Check for core technical keywords that LLM should have picked up
    assert "fastapi" in full_extracted_text
    assert "sqlite" in full_extracted_text or "raw" in full_extracted_text or "transcript" in full_extracted_text
    assert "vad" in full_extracted_text
    
    # Verify metadata tracking
    assert result.metadata.get("local_llm_used") is True
    assert result.metadata.get("llm_endpoint") == service.llm_provider.base_url
    
    print("✅ Real local LLM extraction verified with high-fidelity Turkish technical context.")

if __name__ == "__main__":
    # For manual run
    test_real_local_llm_extraction()
