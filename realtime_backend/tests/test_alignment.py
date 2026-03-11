from app.models import ASRSegment, DiarizationTurn
from app.pipeline.alignment import merge_transcript_segments
from app.pipeline.speaker_mapper import StableSpeakerMapper


def test_alignment_assigns_stable_speakers():
    merged = merge_transcript_segments(
        asr_segments=[
            ASRSegment(start=0.0, end=1.0, text="hello there"),
            ASRSegment(start=1.1, end=2.0, text="hi back"),
        ],
        diarization_turns=[
            DiarizationTurn(start=0.0, end=1.0, speaker="SPEAKER_00"),
            DiarizationTurn(start=1.0, end=2.2, speaker="SPEAKER_01"),
        ],
        speaker_mapper=StableSpeakerMapper(),
        prior_segments=[],
    )

    assert merged[0].speaker == "Speaker_1"
    assert merged[1].speaker == "Speaker_2"
    assert merged[0].corrected_text == "hello there"
