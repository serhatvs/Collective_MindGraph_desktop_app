import pytest
from realtime_backend.app.models import (
    ConversationTranscript,
    TranscriptSegment,
    TaskItem,
    DecisionItem,
    TopicSegment
)
from realtime_backend.app.services.query import KeywordMemoryQueryService

class MockProvider:
    def __init__(self, transcripts):
        self.transcripts = {t.conversation_id: t for t in transcripts}
    def get_transcript(self, conversation_id):
        return self.transcripts.get(conversation_id)

def test_keyword_memory_query_multi_session_turkish():
    # Session A: Technical focus
    transcript_a = ConversationTranscript(
        conversation_id="session_a",
        source="test",
        segments=[
            TranscriptSegment(segment_id="a1", start=0.0, end=5.0, speaker="S1", 
                              corrected_text="Bu hafta FastAPI endpointini test edeceğiz.")
        ],
        action_items=[TaskItem(title="FastAPI endpointini test edeceğiz", source_segment_id="a1")],
        topics=[TopicSegment(label="FastAPI", start=0.0, end=5.0)]
    )
    
    # Session B: Process focus
    transcript_b = ConversationTranscript(
        conversation_id="session_b",
        source="test",
        segments=[
            TranscriptSegment(segment_id="b1", start=0.0, end=5.0, speaker="S2", 
                              corrected_text="SQLite kayıtlarında raw transcript ve cleaned transcript ayrı tutulacak.")
        ],
        decisions=[DecisionItem(decision="raw transcript ve cleaned transcript ayrı tutulacak", source_segment_id="b1")],
        topics=[TopicSegment(label="SQLite", start=0.0, end=5.0)]
    )
    
    service = KeywordMemoryQueryService(MockProvider([transcript_a, transcript_b]))
    conv_ids = ["session_a", "session_b"]
    
    # 1. Query: "FastAPI" -> Should prefer Session A
    results = service.search("FastAPI", conv_ids)
    assert results[0].source_session_id == "session_a"
    assert results[0].matched_terms == ["fastapi"]
    
    # 2. Query: "SQLite" -> Should prefer Session B
    results = service.search("SQLite", conv_ids)
    assert results[0].source_session_id == "session_b"
    
    # 3. Decision prioritization: "raw transcript"
    results = service.search("raw transcript", conv_ids)
    # Decisions get a 1.2 boost, transcript segments 1.0. 
    # Since both match the keywords, decision should be first.
    assert results[0].result_type == "decision"
    assert results[0].source_session_id == "session_b"
    assert results[0].source_segment_id == "b1"
    
    # 4. Negative test: Unrelated query
    results = service.search("unrelated word", conv_ids)
    assert len(results) == 0
    
    # 5. Mixed query specificity
    results = service.search("FastAPI SQLite", conv_ids)
    # Should find items from both
    session_ids = {r.source_session_id for r in results}
    assert "session_a" in session_ids
    assert "session_b" in session_ids

if __name__ == "__main__":
    test_keyword_memory_query_multi_session_turkish()
    print("Keyword memory query tests passed!")
