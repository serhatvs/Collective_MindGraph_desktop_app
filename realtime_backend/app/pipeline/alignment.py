"""Merge ASR and diarization into structured transcript segments."""

from __future__ import annotations

from ..models import ASRSegment, DiarizationTurn, TranscriptSegment
from ..utils.ids import new_segment_id
from ..utils.time import overlap_duration
from .speaker_mapper import StableSpeakerMapper


def merge_transcript_segments(
    asr_segments: list[ASRSegment],
    diarization_turns: list[DiarizationTurn],
    speaker_mapper: StableSpeakerMapper,
    prior_segments: list[TranscriptSegment],
    chunk_offset: float = 0.0,
) -> list[TranscriptSegment]:
    speaker_mapper.begin_chunk(diarization_turns, prior_segments)
    merged: list[TranscriptSegment] = []
    for asr_segment in asr_segments:
        absolute_start = asr_segment.start + chunk_offset
        absolute_end = asr_segment.end + chunk_offset
        speaker_turn = _best_speaker_turn(asr_segment.start, asr_segment.end, diarization_turns)
        raw_speaker = speaker_turn.speaker if speaker_turn is not None else "UNRESOLVED_0"
        stable_speaker = speaker_mapper.resolve(raw_speaker, absolute_start, absolute_end, prior_segments + merged)
        notes: list[str] = []
        if raw_speaker.startswith("UNRESOLVED"):
            notes.append("speaker attribution fell back to unresolved diarization")

        overlap = _has_overlap(asr_segment.start, asr_segment.end, diarization_turns, raw_speaker)
        if overlap:
            notes.append("overlap detected; speaker attribution may be approximate")

        merged.append(
            TranscriptSegment(
                segment_id=new_segment_id(),
                start=absolute_start,
                end=absolute_end,
                speaker=stable_speaker,
                raw_text=asr_segment.text,
                corrected_text=asr_segment.text,
                confidence=asr_segment.confidence,
                speaker_confidence=speaker_turn.confidence if speaker_turn else 0.0,
                overlap=overlap,
                notes=notes,
                metadata={"raw_speaker": raw_speaker},
            )
        )
    return merged


def _best_speaker_turn(start: float, end: float, turns: list[DiarizationTurn]) -> DiarizationTurn | None:
    ranked = sorted(
        turns,
        key=lambda turn: overlap_duration(start, end, turn.start, turn.end),
        reverse=True,
    )
    if not ranked:
        return None
    best = ranked[0]
    return best if overlap_duration(start, end, best.start, best.end) > 0 else None


def _has_overlap(start: float, end: float, turns: list[DiarizationTurn], primary_label: str) -> bool:
    active = [
        turn
        for turn in turns
        if overlap_duration(start, end, turn.start, turn.end) > 0 and turn.speaker != primary_label
    ]
    return bool(active)
