"""Readable transcript formatting helpers."""

from __future__ import annotations

from ..models import (
    ConversationTranscript,
    FileTranscriptionResponse,
    SpeakerStats,
    TranscriptRenderings,
    TranscriptResponse,
    TranscriptSegment,
)
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
        asr_status=transcript.metadata.get("asr_status"),
        warnings=list(transcript.metadata.get("warnings", [])),
        metadata=dict(transcript.metadata),
    )


def build_file_transcription_response(transcript: ConversationTranscript) -> FileTranscriptionResponse:
    response = build_transcript_response(transcript)
    return FileTranscriptionResponse(
        transcript=response.transcript,
        text_output=response.renderings.corrected_text_output,
        raw_text_output=response.renderings.raw_text_output,
        corrected_text_output=response.renderings.corrected_text_output,
        speaker_stats=response.speaker_stats,
        asr_status=response.asr_status,
        warnings=response.warnings,
        metadata=response.metadata,
    )


def build_streaming_transcript_event(
    transcript: ConversationTranscript,
    *,
    is_final: bool,
) -> dict[str, object]:
    response = build_transcript_response(transcript)
    payload: dict[str, object] = {
        "event": "final_transcript" if is_final else "partial_transcript",
        "conversation_id": transcript.conversation_id,
        "segments": [segment.model_dump() for segment in transcript.segments],
    }
    if is_final:
        payload.update(
            {
                "summary": transcript.summary,
                "topics": [topic.model_dump() for topic in transcript.topics],
                "action_items": [item.model_dump() for item in transcript.action_items],
                "decisions": [item.model_dump() for item in transcript.decisions],
                "people": transcript.people,
            }
        )
    payload.update(
        {
            "text_output": response.renderings.corrected_text_output,
            "raw_text_output": response.renderings.raw_text_output,
            "corrected_text_output": response.renderings.corrected_text_output,
            "speaker_stats": [item.model_dump() for item in response.speaker_stats],
            "asr_status": response.asr_status,
            "warnings": response.warnings,
            "metadata": response.metadata,
            "is_final": is_final,
        }
    )
    return payload
