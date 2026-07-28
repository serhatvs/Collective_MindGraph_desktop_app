"""Pure mapping helpers for the canonical transcription archive."""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from collective_mindgraph.application.transcription.contracts import (
    ConversationTranscript,
)
from collective_mindgraph.application.transcription.contracts import (
    TranscriptSegment as ProcessingSegment,
)
from collective_mindgraph.domain import (
    EdgeId,
    EvidenceId,
    KnowledgeNodeId,
    MeetingId,
    SegmentId,
    Transcript,
    TranscriptId,
    TranscriptSegment,
)


def to_domain_transcript(
    result: ConversationTranscript,
    meeting_id: MeetingId,
) -> Transcript:
    raw_text = "\n".join(item.raw_text for item in result.segments if item.raw_text)
    corrected_text = "\n".join(
        item.corrected_text for item in result.segments if item.corrected_text
    )
    diagnostics: dict[str, object] = {
        "source": result.source,
        "quality_mode": result.quality_mode,
        "summary": result.summary,
        **result.metadata,
    }
    if result.diagnostics is not None:
        diagnostics["transcription"] = result.diagnostics.model_dump(mode="json")
    return Transcript(
        id=TranscriptId(0),
        meeting_id=meeting_id,
        conversation_id=result.conversation_id,
        provider=(result.diagnostics.provider if result.diagnostics is not None else "unknown"),
        language=result.language,
        raw_text=raw_text,
        corrected_text=corrected_text,
        confidence=mean_confidence(result),
        diagnostics=diagnostics,
        created_at=result.created_at,
        updated_at=result.updated_at,
        segments=tuple(
            TranscriptSegment(
                id=SegmentId(item.segment_id),
                transcript_id=TranscriptId(0),
                position=index,
                start_seconds=item.start,
                end_seconds=item.end,
                speaker_label=item.speaker,
                raw_text=item.raw_text,
                corrected_text=item.corrected_text,
                confidence=item.confidence,
                speaker_confidence=item.speaker_confidence,
                overlaps_speech=item.overlap,
                notes=tuple(item.notes),
                diagnostics=dict(item.metadata),
            )
            for index, item in enumerate(result.segments)
        ),
    )


def to_processing_segment(segment: TranscriptSegment) -> ProcessingSegment:
    return ProcessingSegment(
        segment_id=str(segment.id),
        start=segment.start_seconds,
        end=segment.end_seconds,
        speaker=segment.speaker_label or "Unknown",
        raw_text=segment.raw_text,
        corrected_text=segment.corrected_text,
        confidence=segment.confidence,
        speaker_confidence=segment.speaker_confidence,
        overlap=segment.overlaps_speech,
        notes=list(segment.notes),
        metadata=dict(segment.diagnostics),
    )


def evidence_id(conversation_id: str, segment_id: str) -> EvidenceId:
    return EvidenceId(str(uuid5(NAMESPACE_URL, f"{conversation_id}:evidence:{segment_id}")))


def meeting_node_id(conversation_id: str) -> KnowledgeNodeId:
    return KnowledgeNodeId(str(uuid5(NAMESPACE_URL, f"{conversation_id}:knowledge:meeting")))


def segment_node_id(conversation_id: str, segment_id: str) -> KnowledgeNodeId:
    return KnowledgeNodeId(
        str(uuid5(NAMESPACE_URL, f"{conversation_id}:knowledge:segment:{segment_id}"))
    )


def person_node_id(conversation_id: str, name: str) -> KnowledgeNodeId:
    return KnowledgeNodeId(
        str(uuid5(NAMESPACE_URL, f"{conversation_id}:knowledge:person:{name.casefold()}"))
    )


def edge_id(
    source_id: KnowledgeNodeId,
    target_id: KnowledgeNodeId,
    kind: str,
) -> EdgeId:
    return EdgeId(str(uuid5(NAMESPACE_URL, f"{source_id}:{kind}:{target_id}")))


def segment_title(segment: TranscriptSegment) -> str:
    speaker = segment.speaker_label or "Speaker"
    return f"{speaker} · {segment.start_seconds:.1f}–{segment.end_seconds:.1f}s"


def segment_at(result: ConversationTranscript, timestamp: float) -> str | None:
    for segment in result.segments:
        if segment.start <= timestamp <= segment.end:
            return segment.segment_id
    return None


def duration_seconds(result: ConversationTranscript) -> float | None:
    return max((segment.end for segment in result.segments), default=None)


def mean_confidence(result: ConversationTranscript) -> float | None:
    values = [item.confidence for item in result.segments if item.confidence is not None]
    return sum(values) / len(values) if values else None


def optional_text(value: object) -> str | None:
    return str(value) if value not in (None, "") else None
