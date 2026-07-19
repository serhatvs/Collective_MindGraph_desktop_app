from app.models import ConversationTranscript, DecisionItem, TaskItem, TopicSegment, TranscriptSegment
from app.pipeline.transcript_formatter import (
    build_file_transcription_response,
    build_speaker_stats,
    build_streaming_transcript_event,
    build_transcript_response,
    format_segment,
    format_transcript,
)


def test_format_segment_renders_expected_text():
    segment = TranscriptSegment(
        segment_id="seg_1",
        start=1.2,
        end=3.8,
        speaker="Speaker_1",
        raw_text="hello there",
        corrected_text="Hello there.",
        confidence=0.91,
    )

    assert format_segment(segment) == "[00:01.200 - 00:03.800] Speaker_1: Hello there."


def test_format_transcript_renders_multiple_lines():
    transcript = ConversationTranscript(
        conversation_id="conv_1",
        source="test",
        segments=[
            TranscriptSegment(
                segment_id="seg_1",
                start=0.0,
                end=1.0,
                speaker="Speaker_1",
                raw_text="hello",
                corrected_text="Hello.",
            ),
            TranscriptSegment(
                segment_id="seg_2",
                start=1.1,
                end=2.0,
                speaker="Speaker_2",
                raw_text="hi",
                corrected_text="Hi.",
            ),
        ],
    )

    rendered = format_transcript(transcript)

    assert "Speaker_1: Hello." in rendered
    assert "Speaker_2: Hi." in rendered


def test_format_transcript_can_render_raw_text():
    transcript = ConversationTranscript(
        conversation_id="conv_1",
        source="test",
        segments=[
            TranscriptSegment(
                segment_id="seg_1",
                start=0.0,
                end=1.0,
                speaker="Speaker_1",
                raw_text="hello there",
                corrected_text="Hello there.",
            )
        ],
    )

    rendered = format_transcript(transcript, corrected=False)

    assert rendered == "[00:00.000 - 00:01.000] Speaker_1: hello there"


def test_build_speaker_stats_aggregates_durations_and_overlap():
    transcript = ConversationTranscript(
        conversation_id="conv_stats",
        source="test",
        segments=[
            TranscriptSegment(
                segment_id="seg_1",
                start=0.0,
                end=1.0,
                speaker="Speaker_1",
                raw_text="hello",
                corrected_text="Hello.",
            ),
            TranscriptSegment(
                segment_id="seg_2",
                start=1.2,
                end=2.7,
                speaker="Speaker_1",
                raw_text="follow up",
                corrected_text="Follow up.",
                overlap=True,
            ),
            TranscriptSegment(
                segment_id="seg_3",
                start=2.8,
                end=3.4,
                speaker="Speaker_2",
                raw_text="hi",
                corrected_text="Hi.",
            ),
        ],
    )

    stats = build_speaker_stats(transcript)

    assert stats[0].speaker == "Speaker_1"
    assert stats[0].segment_count == 2
    assert stats[0].speaking_seconds == 2.5
    assert stats[0].overlap_segments == 1
    assert stats[1].speaker == "Speaker_2"


def test_build_transcript_response_includes_renderings():
    transcript = ConversationTranscript(
        conversation_id="conv_render",
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

    response = build_transcript_response(transcript)

    assert response.renderings.raw_text_output == "[00:00.000 - 00:01.000] Speaker_1: hello"
    assert response.renderings.corrected_text_output == "[00:00.000 - 00:01.000] Speaker_1: Hello."
    assert response.speaker_stats[0].speaker == "Speaker_1"


def test_build_transcript_response_preserves_selective_retranscription_metadata():
    transcript = ConversationTranscript(
        conversation_id="conv_selective",
        source="test",
        metadata={
            "selective_retranscription": {
                "enabled": True,
                "number_of_replaced_segments": 1,
            }
        },
    )

    response = build_transcript_response(transcript)

    assert response.metadata["selective_retranscription"]["enabled"] is True
    assert response.transcript.metadata["selective_retranscription"]["number_of_replaced_segments"] == 1


def test_build_file_transcription_response_preserves_existing_payload_shape():
    transcript = ConversationTranscript(
        conversation_id="conv_file",
        source="upload",
        segments=[
            TranscriptSegment(
                segment_id="seg_file",
                start=0.0,
                end=1.5,
                speaker="Speaker_1",
                raw_text="raw file",
                corrected_text="Corrected file.",
            )
        ],
        metadata={"asr_status": "ASR_STATUS=OK", "warnings": ["sample warning"], "profile": "balanced"},
    )

    response = build_file_transcription_response(transcript)

    assert response.model_dump(mode="json") == {
        "transcript": transcript.model_dump(mode="json"),
        "text_output": "[00:00.000 - 00:01.500] Speaker_1: Corrected file.",
        "raw_text_output": "[00:00.000 - 00:01.500] Speaker_1: raw file",
        "corrected_text_output": "[00:00.000 - 00:01.500] Speaker_1: Corrected file.",
        "speaker_stats": [
            {
                "speaker": "Speaker_1",
                "segment_count": 1,
                "speaking_seconds": 1.5,
                "overlap_segments": 0,
                "first_start": 0.0,
                "last_end": 1.5,
            }
        ],
        "asr_status": "ASR_STATUS=OK",
        "warnings": ["sample warning"],
        "metadata": {
            "asr_status": "ASR_STATUS=OK",
            "warnings": ["sample warning"],
            "profile": "balanced",
        },
    }


def test_build_streaming_transcript_event_preserves_partial_payload_shape():
    transcript = ConversationTranscript(
        conversation_id="conv_partial",
        source="stream",
        segments=[
            TranscriptSegment(
                segment_id="seg_partial",
                start=2.0,
                end=3.0,
                speaker="Speaker_2",
                raw_text="raw partial",
                corrected_text="Corrected partial.",
            )
        ],
        summary="Not included in a partial event.",
        metadata={"asr_status": "ASR_STATUS=OK", "warnings": ["partial warning"]},
    )

    payload = build_streaming_transcript_event(transcript, is_final=False)

    assert payload == {
        "event": "partial_transcript",
        "conversation_id": "conv_partial",
        "segments": [transcript.segments[0].model_dump()],
        "text_output": "[00:02.000 - 00:03.000] Speaker_2: Corrected partial.",
        "raw_text_output": "[00:02.000 - 00:03.000] Speaker_2: raw partial",
        "corrected_text_output": "[00:02.000 - 00:03.000] Speaker_2: Corrected partial.",
        "speaker_stats": [
            {
                "speaker": "Speaker_2",
                "segment_count": 1,
                "speaking_seconds": 1.0,
                "overlap_segments": 0,
                "first_start": 2.0,
                "last_end": 3.0,
            }
        ],
        "asr_status": "ASR_STATUS=OK",
        "warnings": ["partial warning"],
        "metadata": {"asr_status": "ASR_STATUS=OK", "warnings": ["partial warning"]},
        "is_final": False,
    }


def test_build_streaming_transcript_event_preserves_final_payload_shape():
    transcript = ConversationTranscript(
        conversation_id="conv_final",
        source="stream",
        segments=[
            TranscriptSegment(
                segment_id="seg_final",
                start=0.0,
                end=2.0,
                speaker="Speaker_1",
                raw_text="raw final",
                corrected_text="Corrected final.",
            )
        ],
        summary="Final summary.",
        topics=[TopicSegment(label="Testing", start=0.0, end=2.0)],
        action_items=[TaskItem(title="Keep testing", source_segment_id="seg_final")],
        decisions=[DecisionItem(decision="Ship safely", source_segment_id="seg_final")],
        people=["Speaker_1"],
        metadata={"asr_status": "ASR_STATUS=OK"},
    )

    payload = build_streaming_transcript_event(transcript, is_final=True)

    assert payload == {
        "event": "final_transcript",
        "conversation_id": "conv_final",
        "segments": [transcript.segments[0].model_dump()],
        "summary": "Final summary.",
        "topics": [transcript.topics[0].model_dump()],
        "action_items": [transcript.action_items[0].model_dump()],
        "decisions": [transcript.decisions[0].model_dump()],
        "people": ["Speaker_1"],
        "text_output": "[00:00.000 - 00:02.000] Speaker_1: Corrected final.",
        "raw_text_output": "[00:00.000 - 00:02.000] Speaker_1: raw final",
        "corrected_text_output": "[00:00.000 - 00:02.000] Speaker_1: Corrected final.",
        "speaker_stats": [
            {
                "speaker": "Speaker_1",
                "segment_count": 1,
                "speaking_seconds": 2.0,
                "overlap_segments": 0,
                "first_start": 0.0,
                "last_end": 2.0,
            }
        ],
        "asr_status": "ASR_STATUS=OK",
        "warnings": [],
        "metadata": {"asr_status": "ASR_STATUS=OK"},
        "is_final": True,
    }
