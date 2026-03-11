from app.models import ConversationTranscript, TranscriptSegment
from app.pipeline.transcript_formatter import (
    build_speaker_stats,
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
