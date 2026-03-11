"""Readable transcript formatting helpers."""

from __future__ import annotations

from ..models import ConversationTranscript, TranscriptSegment
from ..utils.time import format_timestamp


def format_segment(segment: TranscriptSegment) -> str:
    return (
        f"[{format_timestamp(segment.start)} - {format_timestamp(segment.end)}] "
        f"{segment.speaker}: {segment.corrected_text}"
    )


def format_transcript(transcript: ConversationTranscript) -> str:
    return "\n".join(format_segment(segment) for segment in transcript.segments)
