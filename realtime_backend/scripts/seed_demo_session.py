"""
Seed a demo session using cleaned transcript text.
Simulates a technical Turkish meeting to verify extraction and query.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, UTC

# Ensure we can import from app
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from app.config import get_settings
from app.models import ConversationTranscript, TranscriptSegment
from app.services.conversation_store import ConversationStore
from app.services.summary import ConversationSummaryService

def main():
    settings = get_settings()
    store = ConversationStore(settings.data_dir / "transcripts")
    summary_service = ConversationSummaryService()

    conversation_id = "demo_technical_turkish"
    
    sample_text = (
        "Merhaba, bugün Collective MindGraph toplantısındayız. "
        "Transcript kalitesini artırmamız gerekiyor. "
        "Bu hafta FastAPI endpointini test edeceğiz. "
        "SQLite kayıtlarında raw transcript ve cleaned transcript ayrı tutulacak. "
        "VAD ayarlarını kontrol edip kararları ve görevleri düzgün çıkaracağız."
    )

    # Simulate a processed transcript
    segments = [
        TranscriptSegment(
            segment_id="s1",
            start=0.0,
            end=15.0,
            speaker="Serhat",
            raw_text=sample_text.lower(),
            corrected_text=sample_text
        )
    ]

    transcript = ConversationTranscript(
        conversation_id=conversation_id,
        source="demo_seed",
        language="tr",
        segments=segments,
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC)
    )

    # Run extraction
    summary, topics, action_items, decisions = summary_service.build_summary(transcript)
    transcript.summary = summary
    transcript.topics = topics
    transcript.action_items = action_items
    transcript.decisions = decisions

    # Save
    store.save(transcript)

    print(f"✅ Demo session seeded: {conversation_id}")
    print(f"📄 Summary: {summary}")
    print(f"📋 Tasks: {[t.title for t in action_items]}")
    print(f"💡 Decisions: {[d.decision for d in decisions]}")
    print(f"🏷️ Topics: {[t.label for t in topics]}")
    print(f"\nYou can now search for 'FastAPI' or 'kararlar' in the Desktop UI.")

if __name__ == "__main__":
    main()
