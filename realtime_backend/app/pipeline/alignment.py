"""Merge ASR and diarization into structured transcript segments."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models import ASRSegment, DiarizationTurn, TranscriptSegment
from ..utils.ids import new_segment_id
from ..utils.time import overlap_duration
from .speaker_mapper import StableSpeakerMapper


@dataclass(slots=True)
class _AlignedChunk:
    start: float
    end: float
    text: str
    raw_speaker: str
    words: list = field(default_factory=list)
    speaker_turn: DiarizationTurn | None = None
    overlap: bool = False
    notes: list[str] = field(default_factory=list)
    alignment_source: str = "segment"
    confidence: float | None = None


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
        for chunk in _align_asr_segment(asr_segment, diarization_turns):
            absolute_start = chunk.start + chunk_offset
            absolute_end = chunk.end + chunk_offset
            stable_speaker = speaker_mapper.resolve(
                chunk.raw_speaker,
                absolute_start,
                absolute_end,
                prior_segments + merged,
            )
            notes = list(chunk.notes)
            if chunk.raw_speaker.startswith("UNRESOLVED"):
                notes.append("speaker attribution fell back to unresolved diarization")
            if chunk.overlap:
                notes.append("overlap detected; speaker attribution may be approximate")

            merged.append(
                TranscriptSegment(
                    segment_id=new_segment_id(),
                    start=absolute_start,
                    end=absolute_end,
                    speaker=stable_speaker,
                    raw_text=chunk.text,
                    corrected_text=chunk.text,
                    words=_offset_words(chunk.words, chunk_offset),
                    confidence=chunk.confidence,
                    speaker_confidence=chunk.speaker_turn.confidence if chunk.speaker_turn else 0.0,
                    overlap=chunk.overlap,
                    notes=_unique_notes(notes),
                    metadata={
                        "raw_speaker": chunk.raw_speaker,
                        "alignment_source": chunk.alignment_source,
                    },
                )
            )
    return merged


def _align_asr_segment(
    asr_segment: ASRSegment,
    diarization_turns: list[DiarizationTurn],
) -> list[_AlignedChunk]:
    if not asr_segment.words or not _all_words_timed(asr_segment):
        return [_fallback_chunk(asr_segment, diarization_turns)]

    grouped: list[_AlignedChunk] = []
    current_words = [asr_segment.words[0]]
    current_raw_speaker = _speaker_label_for_span(
        asr_segment.words[0].start or asr_segment.start,
        asr_segment.words[0].end or asr_segment.end,
        diarization_turns,
    )

    for word in asr_segment.words[1:]:
        word_start = word.start or asr_segment.start
        word_end = word.end or asr_segment.end
        raw_speaker = _speaker_label_for_span(word_start, word_end, diarization_turns)
        if raw_speaker == current_raw_speaker:
            current_words.append(word)
            continue
        grouped.append(_chunk_from_words(asr_segment, current_words, current_raw_speaker, diarization_turns))
        current_words = [word]
        current_raw_speaker = raw_speaker

    grouped.append(_chunk_from_words(asr_segment, current_words, current_raw_speaker, diarization_turns))
    if len(grouped) > 1:
        for chunk in grouped:
            chunk.notes.append("split from ASR segment using word timestamps")
    return grouped


def _fallback_chunk(
    asr_segment: ASRSegment,
    diarization_turns: list[DiarizationTurn],
) -> _AlignedChunk:
    speaker_turn = _best_speaker_turn(asr_segment.start, asr_segment.end, diarization_turns)
    raw_speaker = speaker_turn.speaker if speaker_turn is not None else "UNRESOLVED_0"
    return _AlignedChunk(
        start=asr_segment.start,
        end=asr_segment.end,
        text=asr_segment.text,
        raw_speaker=raw_speaker,
        words=asr_segment.words,
        speaker_turn=speaker_turn,
        overlap=_has_overlap(asr_segment.start, asr_segment.end, diarization_turns, raw_speaker),
        alignment_source="segment",
        confidence=asr_segment.confidence,
    )


def _chunk_from_words(
    asr_segment: ASRSegment,
    words,
    raw_speaker: str,
    diarization_turns: list[DiarizationTurn],
) -> _AlignedChunk:
    start = max(asr_segment.start, float(words[0].start or asr_segment.start))
    end = min(asr_segment.end, float(words[-1].end or asr_segment.end))
    if end <= start:
        end = max(start + 0.01, asr_segment.end)
    speaker_turn = _best_speaker_turn(start, end, diarization_turns)
    text = _words_to_text(words) or asr_segment.text
    return _AlignedChunk(
        start=start,
        end=end,
        text=text,
        raw_speaker=raw_speaker,
        words=list(words),
        speaker_turn=speaker_turn,
        overlap=_has_overlap(start, end, diarization_turns, raw_speaker),
        alignment_source="word_timestamps",
        confidence=_average_word_probability(words) or asr_segment.confidence,
    )


def _all_words_timed(asr_segment: ASRSegment) -> bool:
    return all(
        word.start is not None
        and word.end is not None
        and float(word.end) > float(word.start)
        for word in asr_segment.words
    )


def _speaker_label_for_span(
    start: float,
    end: float,
    diarization_turns: list[DiarizationTurn],
) -> str:
    speaker_turn = _best_speaker_turn(start, end, diarization_turns)
    return speaker_turn.speaker if speaker_turn is not None else "UNRESOLVED_0"


def _words_to_text(words) -> str:
    return "".join(word.word for word in words).strip()


def _average_word_probability(words) -> float | None:
    probabilities = [word.probability for word in words if word.probability is not None]
    if not probabilities:
        return None
    return round(sum(probabilities) / len(probabilities), 3)


def _offset_words(words, chunk_offset: float):
    if not chunk_offset:
        return list(words)
    return [
        word.model_copy(
            update={
                "start": (word.start + chunk_offset) if word.start is not None else None,
                "end": (word.end + chunk_offset) if word.end is not None else None,
            }
        )
        for word in words
    ]


def _unique_notes(notes: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for note in notes:
        if note in seen:
            continue
        seen.add(note)
        ordered.append(note)
    return ordered


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
