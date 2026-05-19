from app.models import ConversationTranscript, TranscriptSegment
from app.services.summary import ConversationSummaryService


def test_summary_service_extracts_topics_actions_and_decisions():
    transcript = ConversationTranscript(
        conversation_id="conv_summary",
        source="test",
        segments=[
            TranscriptSegment(
                segment_id="seg_1",
                start=0.0,
                end=2.0,
                speaker="Speaker_1",
                raw_text="we need to ship the release next week",
                corrected_text="We need to ship the release next week.",
            ),
            TranscriptSegment(
                segment_id="seg_2",
                start=2.1,
                end=4.0,
                speaker="Speaker_2",
                raw_text="can you send the final checklist",
                corrected_text="Can you send the final checklist?",
            ),
            TranscriptSegment(
                segment_id="seg_3",
                start=4.2,
                end=6.0,
                speaker="Speaker_1",
                raw_text="we will freeze scope today",
                corrected_text="We will freeze scope today.",
            ),
        ],
    )

    service = ConversationSummaryService()
    summary, topics, action_items, decisions = service.build_summary(transcript)

    assert summary is not None
    assert "Technical conversation covered" in summary
    assert topics
    # Speaker_1/2 are generic, so they should be mapped to Unassigned
    assert all(item.responsible_person == "Unassigned" for item in action_items)
    assert any("freeze scope today" in item.decision.lower() for item in decisions)

