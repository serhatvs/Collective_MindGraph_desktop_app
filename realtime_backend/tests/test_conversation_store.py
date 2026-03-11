from app.models import ConversationTranscript, TranscriptSegment
from app.services.conversation_store import ConversationStore


def test_conversation_store_round_trips_transcript(tmp_path):
    store = ConversationStore(tmp_path)
    transcript = ConversationTranscript(
        conversation_id="conv_123",
        source="test",
        segments=[
            TranscriptSegment(
                segment_id="seg_1",
                start=0.0,
                end=1.0,
                speaker="Speaker_1",
                raw_text="hello",
                corrected_text="Hello.",
            )
        ],
    )

    store.save(transcript)
    loaded = store.get("conv_123")

    assert loaded is not None
    assert loaded.conversation_id == "conv_123"
    assert loaded.segments[0].corrected_text == "Hello."
