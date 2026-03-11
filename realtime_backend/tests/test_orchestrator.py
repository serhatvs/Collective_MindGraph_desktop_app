from app.models import SpeechRegion, TranscriptSegment
from app.pipeline.orchestrator import _build_processing_windows, _clip_regions_to_window, _replace_timeline_tail


def test_build_processing_windows_groups_regions_into_bounded_spans():
    windows = _build_processing_windows(
        total_duration=210.0,
        regions=[
            SpeechRegion(start=4.0, end=18.0),
            SpeechRegion(start=21.0, end=39.0),
            SpeechRegion(start=98.0, end=120.0),
            SpeechRegion(start=125.0, end=154.0),
        ],
        max_window_seconds=45.0,
        overlap_seconds=2.0,
    )

    assert [(round(item.start, 1), round(item.end, 1)) for item in windows] == [
        (2.0, 41.0),
        (96.0, 122.0),
        (123.0, 156.0),
    ]


def test_clip_regions_to_window_offsets_to_local_coordinates():
    clipped = _clip_regions_to_window(
        regions=[
            SpeechRegion(start=8.0, end=12.0),
            SpeechRegion(start=14.0, end=19.0),
            SpeechRegion(start=26.0, end=30.0),
        ],
        window_start=10.0,
        window_end=25.0,
    )

    assert [(item.start, item.end) for item in clipped] == [
        (0.0, 2.0),
        (4.0, 9.0),
    ]


def test_replace_timeline_tail_replaces_boundary_crossing_segments():
    existing = [
        TranscriptSegment(
            segment_id="seg_1",
            start=0.0,
            end=10.0,
            speaker="Speaker_1",
            raw_text="opening",
            corrected_text="opening",
        ),
        TranscriptSegment(
            segment_id="seg_2",
            start=10.0,
            end=16.0,
            speaker="Speaker_2",
            raw_text="replace me",
            corrected_text="replace me",
        ),
    ]
    incoming = [
        TranscriptSegment(
            segment_id="seg_3",
            start=12.0,
            end=18.0,
            speaker="Speaker_2",
            raw_text="fresh",
            corrected_text="fresh",
        )
    ]

    replaced = _replace_timeline_tail(existing, incoming, from_second=12.0)

    assert [item.segment_id for item in replaced] == ["seg_1", "seg_3"]
