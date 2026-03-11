from app.models import ASRSegment, DiarizationTurn, WordTimestamp
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


def test_alignment_splits_asr_segment_on_word_level_speaker_change():
    merged = merge_transcript_segments(
        asr_segments=[
            ASRSegment(
                start=0.0,
                end=1.6,
                text="hello there hi back",
                words=[
                    WordTimestamp(start=0.0, end=0.3, word="hello ", probability=0.9),
                    WordTimestamp(start=0.3, end=0.7, word="there ", probability=0.92),
                    WordTimestamp(start=1.0, end=1.2, word="hi ", probability=0.88),
                    WordTimestamp(start=1.2, end=1.6, word="back", probability=0.9),
                ],
            ),
        ],
        diarization_turns=[
            DiarizationTurn(start=0.0, end=0.8, speaker="SPEAKER_00"),
            DiarizationTurn(start=0.95, end=1.7, speaker="SPEAKER_01"),
        ],
        speaker_mapper=StableSpeakerMapper(),
        prior_segments=[],
    )

    assert len(merged) == 2
    assert merged[0].speaker == "Speaker_1"
    assert merged[0].raw_text == "hello there"
    assert merged[0].start == 0.0
    assert merged[0].end == 0.7
    assert merged[0].metadata["alignment_source"] == "word_timestamps"
    assert [word.word for word in merged[0].words] == ["hello ", "there "]

    assert merged[1].speaker == "Speaker_2"
    assert merged[1].raw_text == "hi back"
    assert merged[1].start == 1.0
    assert merged[1].end == 1.6
    assert merged[1].metadata["alignment_source"] == "word_timestamps"
