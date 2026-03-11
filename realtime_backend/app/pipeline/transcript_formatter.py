"""Readable transcript formatting helpers."""

from __future__ import annotations

from ..models import ConversationTranscript, SpeakerStats, TranscriptRenderings, TranscriptResponse, TranscriptSegment
from ..utils.time import format_timestamp


def format_segment(segment: TranscriptSegment, *, corrected: bool = True) -> str:
    text = segment.corrected_text if corrected else segment.raw_text
    return (
        f"[{format_timestamp(segment.start)} - {format_timestamp(segment.end)}] "
        f"{segment.speaker}: {text}"
    )


def format_transcript(transcript: ConversationTranscript, *, corrected: bool = True) -> str:
    return "\n".join(format_segment(segment, corrected=corrected) for segment in transcript.segments)


def build_renderings(transcript: ConversationTranscript) -> TranscriptRenderings:
    return TranscriptRenderings(
        raw_text_output=format_transcript(transcript, corrected=False),
        corrected_text_output=format_transcript(transcript, corrected=True),
    )


def build_speaker_stats(transcript: ConversationTranscript) -> list[SpeakerStats]:
    stats: dict[str, SpeakerStats] = {}
    speaker_order: list[str] = []
    for segment in transcript.segments:
        if segment.speaker not in stats:
            stats[segment.speaker] = SpeakerStats(
                speaker=segment.speaker,
                segment_count=0,
                speaking_seconds=0.0,
                overlap_segments=0,
                first_start=segment.start,
                last_end=segment.end,
            )
            speaker_order.append(segment.speaker)
        item = stats[segment.speaker]
        item.segment_count += 1
        item.speaking_seconds = round(item.speaking_seconds + max(0.0, segment.end - segment.start), 3)
        item.overlap_segments += int(segment.overlap)
        item.first_start = min(item.first_start, segment.start)
        item.last_end = max(item.last_end, segment.end)
    return [stats[speaker] for speaker in speaker_order]


def build_transcript_response(transcript: ConversationTranscript) -> TranscriptResponse:
    return TranscriptResponse(
        transcript=transcript,
        renderings=build_renderings(transcript),
        speaker_stats=build_speaker_stats(transcript),
    )
