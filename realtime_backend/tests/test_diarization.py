from app.models import DiarizationTurn, SpeechRegion
from app.pipeline.diarization import _postprocess_turns, _regions_for_diarization


def test_regions_for_diarization_merge_and_split_windows():
    windows = _regions_for_diarization(
        [
            SpeechRegion(start=1.0, end=4.0, confidence=0.8),
            SpeechRegion(start=4.2, end=7.0, confidence=0.7),
            SpeechRegion(start=12.0, end=30.0, confidence=0.9),
        ],
        padding_seconds=0.25,
        merge_gap_seconds=0.8,
        max_window_seconds=10.0,
    )

    assert len(windows) == 3
    assert windows[0].start == 0.75
    assert windows[0].end == 7.25
    assert (windows[1].end - windows[1].start) <= 10.0
    assert (windows[2].end - windows[2].start) <= 10.0


def test_postprocess_turns_merges_duplicates_and_marks_overlap():
    turns = _postprocess_turns(
        [
            DiarizationTurn(start=0.0, end=1.0, speaker="SPEAKER_00", confidence=0.9),
            DiarizationTurn(start=0.05, end=1.02, speaker="SPEAKER_00", confidence=0.8),
            DiarizationTurn(start=1.1, end=2.0, speaker="SPEAKER_00", confidence=0.9),
            DiarizationTurn(start=1.4, end=2.2, speaker="SPEAKER_01", confidence=0.9),
        ],
        overlap_threshold=0.30,
    )

    assert len(turns) == 2
    assert turns[0].speaker == "SPEAKER_00"
    assert turns[0].end == 2.0
    assert turns[0].overlap is True
    assert turns[1].speaker == "SPEAKER_01"
    assert turns[1].overlap is True
