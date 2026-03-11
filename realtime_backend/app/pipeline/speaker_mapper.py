"""Stable speaker mapping across chunked processing windows."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models import DiarizationTurn, TranscriptSegment
from ..utils.time import overlap_duration, overlap_ratio

_OVERLAP_WEIGHT = 3.0
_RECENCY_WEIGHT = 0.4
_PROFILE_WEIGHT = 0.25
_REUSE_THRESHOLD = 0.35
_RECENCY_WINDOW_SECONDS = 1.5


@dataclass
class SpeakerProfile:
    speaker: str
    last_start: float
    last_end: float
    segment_count: int = 0


@dataclass
class StableSpeakerMapper:
    next_speaker_index: int = 1
    chunk_assignments: dict[str, str] = field(default_factory=dict)
    speaker_profiles: dict[str, SpeakerProfile] = field(default_factory=dict)

    def reset_chunk(self) -> None:
        self.chunk_assignments.clear()

    def begin_chunk(
        self,
        diarization_turns: list[DiarizationTurn],
        prior_segments: list[TranscriptSegment],
    ) -> None:
        self.reset_chunk()
        self._sync_next_index(prior_segments)
        grouped_turns = _group_turns_by_label(diarization_turns)
        if not grouped_turns:
            return

        candidates = {segment.speaker for segment in prior_segments}
        candidates.update(self.speaker_profiles)
        if not candidates:
            return

        scored_labels: list[tuple[str, list[tuple[str, float]]]] = []
        for raw_label, turns in grouped_turns.items():
            scores: list[tuple[str, float]] = []
            for stable_speaker in candidates:
                score = self._score_candidate(stable_speaker, turns, prior_segments)
                if score > 0:
                    scores.append((stable_speaker, score))
            scores.sort(key=lambda item: item[1], reverse=True)
            scored_labels.append((raw_label, scores))

        used_stable_speakers: set[str] = set()
        for raw_label, scores in sorted(
            scored_labels,
            key=lambda item: item[1][0][1] if item[1] else 0.0,
            reverse=True,
        ):
            for stable_speaker, score in scores:
                if stable_speaker in used_stable_speakers:
                    continue
                if score < _REUSE_THRESHOLD:
                    break
                self.chunk_assignments[raw_label] = stable_speaker
                used_stable_speakers.add(stable_speaker)
                break

    def resolve(
        self,
        raw_label: str,
        start: float,
        end: float,
        prior_segments: list[TranscriptSegment],
    ) -> str:
        if raw_label in self.chunk_assignments:
            stable = self.chunk_assignments[raw_label]
            self.record_segment(stable, start, end)
            return stable

        for segment in reversed(prior_segments):
            if overlap_duration(start, end, segment.start, segment.end) > 0.2:
                self.chunk_assignments[raw_label] = segment.speaker
                self.record_segment(segment.speaker, start, end)
                return segment.speaker
            if abs(segment.start - start) < 0.5:
                self.chunk_assignments[raw_label] = segment.speaker
                self.record_segment(segment.speaker, start, end)
                return segment.speaker

        fallback_speaker = self._nearest_profile_speaker(
            start,
            end,
            exclude=set(self.chunk_assignments.values()),
        )
        if fallback_speaker is not None:
            self.chunk_assignments[raw_label] = fallback_speaker
            self.record_segment(fallback_speaker, start, end)
            return fallback_speaker

        stable = f"Speaker_{self.next_speaker_index}"
        self.next_speaker_index += 1
        self.chunk_assignments[raw_label] = stable
        self.record_segment(stable, start, end)
        return stable

    def record_segment(self, stable_speaker: str, start: float, end: float) -> None:
        self._reserve_speaker_id(stable_speaker)
        profile = self.speaker_profiles.get(stable_speaker)
        if profile is None:
            self.speaker_profiles[stable_speaker] = SpeakerProfile(
                speaker=stable_speaker,
                last_start=start,
                last_end=end,
                segment_count=1,
            )
            return
        profile.last_start = start
        profile.last_end = max(profile.last_end, end)
        profile.segment_count += 1

    def _score_candidate(
        self,
        stable_speaker: str,
        turns: list[DiarizationTurn],
        prior_segments: list[TranscriptSegment],
    ) -> float:
        score = 0.0
        candidate_segments = [segment for segment in prior_segments if segment.speaker == stable_speaker]
        for turn in turns:
            for segment in reversed(candidate_segments[-12:]):
                overlap = overlap_duration(turn.start, turn.end, segment.start, segment.end)
                if overlap > 0:
                    score += overlap * _OVERLAP_WEIGHT
                    score += overlap_ratio(turn.start, turn.end, segment.start, segment.end)
                    continue
                gap = min(abs(turn.start - segment.end), abs(segment.start - turn.end))
                if gap <= _RECENCY_WINDOW_SECONDS:
                    score += max(0.0, _RECENCY_WINDOW_SECONDS - gap) * _RECENCY_WEIGHT

        profile = self.speaker_profiles.get(stable_speaker)
        if profile is not None:
            nearest_gap = min(abs(turn.start - profile.last_end) for turn in turns)
            if nearest_gap <= _RECENCY_WINDOW_SECONDS:
                score += max(0.0, _RECENCY_WINDOW_SECONDS - nearest_gap) * _PROFILE_WEIGHT
        return score

    def _nearest_profile_speaker(
        self,
        start: float,
        end: float,
        exclude: set[str] | None = None,
    ) -> str | None:
        best_speaker: str | None = None
        best_gap: float | None = None
        blocked = exclude or set()
        for speaker, profile in self.speaker_profiles.items():
            if speaker in blocked:
                continue
            gap = min(abs(start - profile.last_end), abs(profile.last_start - end))
            if gap > _RECENCY_WINDOW_SECONDS:
                continue
            if best_gap is None or gap < best_gap:
                best_gap = gap
                best_speaker = speaker
        return best_speaker

    def _sync_next_index(self, prior_segments: list[TranscriptSegment]) -> None:
        for segment in prior_segments:
            self._reserve_speaker_id(segment.speaker)
        for speaker in self.speaker_profiles:
            self._reserve_speaker_id(speaker)

    def _reserve_speaker_id(self, stable_speaker: str) -> None:
        if not stable_speaker.startswith("Speaker_"):
            return
        suffix = stable_speaker.removeprefix("Speaker_")
        if not suffix.isdigit():
            return
        self.next_speaker_index = max(self.next_speaker_index, int(suffix) + 1)


def _group_turns_by_label(diarization_turns: list[DiarizationTurn]) -> dict[str, list[DiarizationTurn]]:
    grouped: dict[str, list[DiarizationTurn]] = {}
    for turn in diarization_turns:
        grouped.setdefault(turn.speaker, []).append(turn)
    return grouped
