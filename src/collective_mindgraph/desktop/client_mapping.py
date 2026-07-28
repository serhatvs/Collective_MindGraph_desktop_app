"""Translate versioned engine payloads into desktop contracts."""

from __future__ import annotations

from datetime import datetime

from .contracts import (
    EnginePreferencesSnapshot,
    EvidenceItem,
    InsightItem,
    MeetingSummary,
    MeetingTranscript,
    ProcessingJob,
    TranscriptSegment,
)


def object_list(value: object) -> list[dict[str, object]]:
    return [dict(item) for item in value] if isinstance(value, list) else []


def optional_text(value: object) -> str | None:
    return str(value) if value not in (None, "") else None


def meeting(payload: dict[str, object]) -> MeetingSummary:
    return MeetingSummary(
        id=int(payload["id"]),
        title=str(payload["title"]),
        status=str(payload["status"]),
        input_device=optional_text(payload.get("input_device")),
        created_at=parse_datetime(payload["created_at"]),
        updated_at=parse_datetime(payload["updated_at"]),
    )


def segment(payload: dict[str, object]) -> TranscriptSegment:
    return TranscriptSegment(
        id=str(payload["id"]),
        position=int(payload["position"]),
        start_seconds=float(payload["start_seconds"]),
        end_seconds=float(payload["end_seconds"]),
        speaker_label=optional_text(payload.get("speaker_label")),
        raw_text=str(payload.get("raw_text") or ""),
        corrected_text=str(payload.get("corrected_text") or ""),
        confidence=(
            float(payload["confidence"]) if payload.get("confidence") is not None else None
        ),
        needs_review=bool(payload.get("needs_review", False)),
    )


def transcript(payload: dict[str, object]) -> MeetingTranscript:
    return MeetingTranscript(
        id=int(payload["id"]),
        meeting_id=int(payload["meeting_id"]),
        conversation_id=optional_text(payload.get("conversation_id")),
        provider=str(payload["provider"]),
        language=optional_text(payload.get("language")),
        raw_text=str(payload.get("raw_text") or ""),
        corrected_text=str(payload.get("corrected_text") or ""),
        segments=tuple(segment(item) for item in object_list(payload.get("segments"))),
    )


def processing_job(payload: dict[str, object]) -> ProcessingJob:
    return ProcessingJob(
        id=str(payload["id"]),
        meeting_id=(int(payload["meeting_id"]) if payload.get("meeting_id") is not None else None),
        recording_id=optional_text(payload.get("recording_id")),
        parent_job_id=optional_text(payload.get("parent_job_id")),
        result_transcript_id=(
            int(payload["result_transcript_id"])
            if payload.get("result_transcript_id") is not None
            else None
        ),
        kind=str(payload["kind"]),
        status=str(payload["status"]),
        progress=int(payload["progress"]),
        message=str(payload.get("message") or ""),
        error=optional_text(payload.get("error")),
        retryable=bool(payload.get("retryable", False)),
        created_at=parse_datetime(payload["created_at"]),
        updated_at=parse_datetime(payload["updated_at"]),
    )


def insight(payload: dict[str, object]) -> InsightItem:
    return InsightItem(
        id=str(payload["id"]),
        meeting_id=int(payload["meeting_id"]),
        kind=str(payload["kind"]),
        title=str(payload["title"]),
        body=str(payload["body"]),
        review=str(payload["review"]),
        needs_review=bool(payload["needs_review"]),
        confidence=(
            float(payload["confidence"]) if payload.get("confidence") is not None else None
        ),
        evidence_id=optional_text(payload.get("evidence_id")),
    )


def evidence(payload: dict[str, object]) -> EvidenceItem:
    return EvidenceItem(
        id=str(payload["id"]),
        meeting_id=int(payload["meeting_id"]),
        segment_id=optional_text(payload.get("segment_id")),
        start_seconds=(
            float(payload["start_seconds"]) if payload.get("start_seconds") is not None else None
        ),
        end_seconds=(
            float(payload["end_seconds"]) if payload.get("end_seconds") is not None else None
        ),
        text_preview=optional_text(payload.get("text_preview")),
        confidence=(
            float(payload["confidence"]) if payload.get("confidence") is not None else None
        ),
        extractor=optional_text(payload.get("extractor")),
        created_at=parse_datetime(payload["created_at"]),
    )


def preferences(payload: dict[str, object]) -> EnginePreferencesSnapshot:
    return EnginePreferencesSnapshot(
        language=optional_text(payload.get("language")),
        transcription_quality=str(payload["transcription_quality"]),
        asr_provider=str(payload["asr_provider"]),
        asr_model=str(payload["asr_model"]),
        embeddings_enabled=bool(payload["embeddings_enabled"]),
        embedding_provider=str(payload["embedding_provider"]),
        local_llm_provider=str(payload["local_llm_provider"]),
        diarization_enabled=bool(payload["diarization_enabled"]),
        retain_raw_audio=bool(payload.get("retain_raw_audio", False)),
    )


def parse_datetime(value: object) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
