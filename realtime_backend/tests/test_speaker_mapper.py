from app.models import DiarizationTurn, TranscriptSegment
from app.pipeline.speaker_mapper import StableSpeakerMapper


def test_begin_chunk_reuses_stable_speakers_when_raw_labels_flip():
    mapper = StableSpeakerMapper()
    prior_segments = [
        TranscriptSegment(
            segment_id="seg_1",
            start=10.0,
            end=11.3,
            speaker="Speaker_1",
            raw_text="hello",
            corrected_text="hello",
        ),
        TranscriptSegment(
            segment_id="seg_2",
            start=11.3,
            end=12.4,
            speaker="Speaker_2",
            raw_text="hi there",
            corrected_text="hi there",
        ),
    ]
    mapper.record_segment("Speaker_1", 10.0, 11.3)
    mapper.record_segment("Speaker_2", 11.3, 12.4)

    mapper.begin_chunk(
        diarization_turns=[
            DiarizationTurn(start=10.2, end=11.2, speaker="SPEAKER_01", confidence=1.0),
            DiarizationTurn(start=11.2, end=12.5, speaker="SPEAKER_00", confidence=1.0),
        ],
        prior_segments=prior_segments,
    )

    assert mapper.resolve("SPEAKER_01", 10.2, 11.2, prior_segments) == "Speaker_1"
    assert mapper.resolve("SPEAKER_00", 11.2, 12.5, prior_segments) == "Speaker_2"


def test_resolve_creates_new_speaker_when_no_reliable_prior_match_exists():
    mapper = StableSpeakerMapper()
    prior_segments = [
        TranscriptSegment(
            segment_id="seg_1",
            start=0.0,
            end=1.0,
            speaker="Speaker_1",
            raw_text="opening",
            corrected_text="opening",
        )
    ]
    mapper.record_segment("Speaker_1", 0.0, 1.0)

    mapper.begin_chunk(
        diarization_turns=[DiarizationTurn(start=8.0, end=9.0, speaker="SPEAKER_99", confidence=1.0)],
        prior_segments=prior_segments,
    )

    assert mapper.resolve("SPEAKER_99", 8.0, 9.0, prior_segments) == "Speaker_2"
