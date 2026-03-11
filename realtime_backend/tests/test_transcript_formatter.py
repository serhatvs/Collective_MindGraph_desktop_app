from app.models import ConversationTranscript, TranscriptSegment
from app.pipeline.transcript_formatter import format_segment, format_transcript


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
