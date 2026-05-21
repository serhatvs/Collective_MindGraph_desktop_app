"""
Verify AI Extraction Service mode and output.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src and backend to path
sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))
sys.path.append(str(Path(__file__).resolve().parents[1]))

from realtime_backend.app.pipeline.extraction import AIExtractionService
from realtime_backend.app.models import ConversationTranscript, TranscriptSegment
from realtime_backend.app.config import get_settings

async def main():
    print("--- Collective MindGraph AI Extraction Verification ---")
    
    settings = get_settings()
    service = AIExtractionService(settings)
    
    # Sample Transcript
    transcript = ConversationTranscript(
        conversation_id="test_verify",
        source="verification_script",
        segments=[
            TranscriptSegment(
                segment_id="s1", start=0, end=5, speaker="Serhat",
                corrected_text="Bugün FastAPI endpointlerini test edeceğiz."
            ),
            TranscriptSegment(
                segment_id="s2", start=5, end=10, speaker="Ali",
                corrected_text="Tamam, SQLite veritabanı yedeğini aldım."
            )
        ]
    )
    
    print(f"Extraction Mode: {service.mode}")
    print(f"Input Segments: {len(transcript.segments)}")
    
    result = await service.extract_intelligence(transcript)
    
    print("\n--- RESULTS ---")
    print(f"Extraction Source: {result.metadata.get('extraction_source')}")
    if "extraction_fallback_reason" in result.metadata:
        print(f"Fallback Reason: {result.metadata['extraction_fallback_reason']}")
    
    print(f"Summary: {result.summary}")
    print(f"Tasks: {[t.title for t in result.action_items]}")
    print(f"Decisions: {[d.decision for d in result.decisions]}")
    print(f"Topics: {[t.label for t in result.topics]}")

if __name__ == "__main__":
    asyncio.run(main())
