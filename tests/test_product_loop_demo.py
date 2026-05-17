import pytest
from pathlib import Path
from realtime_backend.app.config import Settings
from realtime_backend.app.models import (
    ConversationTranscript,
    TranscriptSegment,
    TaskItem,
    DecisionItem,
    TopicSegment
)
from realtime_backend.app.services.summary import ConversationSummaryService
from realtime_backend.app.services.query import KeywordMemoryQueryService

class MockProvider:
    def __init__(self, transcript):
        self.transcript = transcript
    def get_transcript(self, conversation_id):
        return self.transcript

def test_full_product_loop_demo_logic():
    # 1. Input: Technical Turkish Transcript
    sample_text = (
        "Merhaba, bugün Collective MindGraph toplantısındayız. "
        "Bu hafta FastAPI endpointini test edeceğiz. "
        "SQLite kayıtlarında raw transcript ve cleaned transcript ayrı tutulacak. "
        "VAD ayarlarını kontrol edip kararları ve görevleri düzgün çıkaracağız."
    )
    
    segments = [
        TranscriptSegment(
            segment_id="s1",
            start=0.0,
            end=10.0,
            speaker="Serhat",
            raw_text=sample_text.lower(),
            corrected_text=sample_text
        )
    ]
    
    transcript = ConversationTranscript(
        conversation_id="demo_loop",
        source="test",
        segments=segments,
        language="tr"
    )
    
    # 2. Extraction Step
    summary_service = ConversationSummaryService()
    summary, topics, action_items, decisions = summary_service.build_summary(transcript)
    transcript.summary = summary
    transcript.topics = topics
    transcript.action_items = action_items
    transcript.decisions = decisions
    
    assert "covered" in summary.lower() or "konuşuldu" in summary.lower()
    assert any("fastapi" in t.title.lower() for t in action_items)
    assert any("sqlite" in d.decision.lower() for d in decisions)
    
    # 3. Query Step
    query_service = KeywordMemoryQueryService(MockProvider(transcript))
    
    # Query: "FastAPI endpoint" -> Should return task
    res_task = query_service.search("FastAPI endpoint", ["demo_loop"])
    print(f"\nQuery 'FastAPI endpoint' results: {[(r.result_type, r.text) for r in res_task]}")
    assert any(r.result_type == "task" and "fastapi" in r.text.lower() for r in res_task)
    
    # Query: "raw transcript" -> Should return decision
    res_decision = query_service.search("raw transcript", ["demo_loop"])
    print(f"Query 'raw transcript' results: {[(r.result_type, r.text) for r in res_decision]}")
    assert any(r.result_type == "decision" and "raw transcript" in r.text.lower() for r in res_decision)
    
    # 4. Source Traceability
    for r in res_task:
        assert r.source_session_id == "demo_loop"
        assert r.source_segment_id == "s1"
        assert r.matched_field in ["title", "corrected_text"]

if __name__ == "__main__":
    test_full_product_loop_demo_logic()
    print("Full product loop demo smoke test passed!")
