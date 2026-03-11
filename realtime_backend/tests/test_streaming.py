from app.config import Settings
from app.models import TranscriptSegment
from app.services.streaming import StreamSession, StreamingTranscriptionService


def test_replace_tail_drops_segments_that_cross_reprocess_boundary():
    existing = [
        TranscriptSegment(
            segment_id="seg_1",
            start=0.0,
            end=2.5,
            speaker="Speaker_1",
            raw_text="opening",
            corrected_text="opening",
        ),
        TranscriptSegment(
            segment_id="seg_2",
            start=2.8,
            end=4.1,
            speaker="Speaker_2",
            raw_text="boundary",
            corrected_text="boundary",
        ),
    ]
    incoming = [
        TranscriptSegment(
            segment_id="seg_3",
            start=2.7,
            end=3.6,
            speaker="Speaker_2",
            raw_text="reprocessed",
            corrected_text="reprocessed",
        )
    ]

    replaced = StreamingTranscriptionService._replace_tail(existing, incoming, from_second=3.0)

    assert [segment.segment_id for segment in replaced] == ["seg_1", "seg_3"]


def test_window_start_uses_bounded_recent_history():
    service = object.__new__(StreamingTranscriptionService)
    service._settings = Settings(
        stream_partial_window_seconds=8.0,
        stream_overlap_seconds=1.5,
    )
    session = StreamSession(conversation_id="conv_1", language="en")
    session.buffer_start_seconds = 0.0
    session.committed_seconds = 20.0

    window_start = service._window_start_seconds(session, buffer_end=24.0, finalize=False)

    assert window_start == 16.0


def test_compact_buffer_keeps_recent_audio_only():
    service = object.__new__(StreamingTranscriptionService)
    service._settings = Settings(
        sample_rate=16_000,
        channels=1,
        sample_width_bytes=2,
        stream_partial_window_seconds=8.0,
        stream_overlap_seconds=1.5,
        stream_buffer_retention_seconds=12.0,
    )
    session = StreamSession(conversation_id="conv_2", language="en")
    bytes_per_second = (
        service._settings.sample_rate * service._settings.channels * service._settings.sample_width_bytes
    )
    session.pcm_buffer = bytearray(b"\x00" * int(bytes_per_second * 20))

    service._compact_buffer(session, buffer_end=20.0)

    assert round(session.buffer_start_seconds, 3) == 8.0
    assert len(session.pcm_buffer) == int(bytes_per_second * 12)
