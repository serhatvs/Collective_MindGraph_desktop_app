from app.models import ConversationTranscript, TranscriptSegment, WordTimestamp
from app.services.quality import TranscriptQualityService


def test_quality_service_builds_operational_metrics_and_warnings():
    transcript = ConversationTranscript(
        conversation_id="conv_quality",
        source="test",
        summary="A short summary.",
        action_items=["Speaker_1: Send the report"],
        decisions=["Speaker_2: Freeze scope"],
        segments=[
            TranscriptSegment(
                segment_id="seg_1",
                start=0.0,
                end=1.5,
                speaker="Speaker_1",
                raw_text="send the report",
                corrected_text="Send the report.",
                confidence=0.82,
                speaker_confidence=0.9,
                words=[WordTimestamp(start=0.0, end=0.2, word="send", probability=0.9)],
            ),
            TranscriptSegment(
                segment_id="seg_2",
                start=1.6,
                end=3.0,
                speaker="UNRESOLVED_0",
                raw_text="okay",
                corrected_text="Okay?",
                confidence=0.58,
                speaker_confidence=0.4,
                overlap=True,
            ),
        ],
    )

    service = TranscriptQualityService()
    report = service.build_report(transcript)

    assert report.segment_count == 2
    assert report.speaker_count == 2
    assert report.unresolved_segments == 1
    assert report.topic_count == 0
    assert report.action_item_count == 1
    assert report.decision_count == 1
    assert report.summary_present is True
    assert report.warnings


def test_quality_service_can_compare_against_reference():
    transcript = ConversationTranscript(
        conversation_id="conv_live",
        source="test",
        summary="We agreed to ship next week.",
        action_items=["Speaker_1: Send the checklist"],
        segments=[
            TranscriptSegment(
                segment_id="seg_1",
                start=0.0,
                end=1.0,
                speaker="Speaker_1",
                raw_text="send the checklist",
                corrected_text="Send the checklist.",
            )
        ],
    )
    reference = ConversationTranscript(
        conversation_id="conv_ref",
        source="test",
        summary="We agreed to ship next week.",
        action_items=["Speaker_1: Send the checklist"],
        segments=[
            TranscriptSegment(
                segment_id="seg_r1",
                start=0.0,
                end=1.0,
                speaker="Speaker_1",
                raw_text="send the checklist",
                corrected_text="Send the checklist.",
            )
        ],
    )

    report = TranscriptQualityService().build_report(transcript, reference=reference)

    assert report.comparison is not None
    assert report.comparison.text_overlap == 1.0
    assert report.comparison.speaker_match_ratio == 1.0
