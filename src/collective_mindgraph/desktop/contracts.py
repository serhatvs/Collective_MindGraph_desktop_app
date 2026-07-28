"""Typed values exchanged between the desktop shell and local engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class EngineSettings:
    base_url: str = "http://127.0.0.1:8080"
    timeout_seconds: float = 30.0


@dataclass(frozen=True, slots=True)
class TranscriptionPreferences:
    language: str | None = None
    quality_mode: str | None = None
    glossary: tuple[str, ...] = ()
    hotwords: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MeetingSummary:
    id: int
    title: str
    status: str
    input_device: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    id: str
    position: int
    start_seconds: float
    end_seconds: float
    raw_text: str
    corrected_text: str
    speaker_label: str | None = None
    confidence: float | None = None
    needs_review: bool = False


@dataclass(frozen=True, slots=True)
class MeetingTranscript:
    id: int
    meeting_id: int
    conversation_id: str | None
    provider: str
    language: str | None
    raw_text: str
    corrected_text: str
    segments: tuple[TranscriptSegment, ...]


@dataclass(frozen=True, slots=True)
class ProcessingJob:
    id: str
    meeting_id: int | None
    recording_id: str | None
    parent_job_id: str | None
    result_transcript_id: int | None
    kind: str
    status: str
    progress: int
    message: str
    error: str | None
    retryable: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class InsightItem:
    id: str
    meeting_id: int
    kind: str
    title: str
    body: str
    review: str
    needs_review: bool
    confidence: float | None = None
    evidence_id: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    id: str
    meeting_id: int
    segment_id: str | None
    start_seconds: float | None
    end_seconds: float | None
    text_preview: str | None
    confidence: float | None
    extractor: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class KnowledgeItem:
    id: str
    kind: str
    title: str
    body: str
    meeting_id: int | None
    evidence_id: str | None
    attributes: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class KnowledgeRelationship:
    id: str
    source_id: str
    target_id: str
    kind: str
    confidence: float
    evidence_id: str | None = None


@dataclass(frozen=True, slots=True)
class MemorySearchItem:
    id: str
    kind: str
    text: str
    score: float
    meeting_id: str
    segment_id: str | None
    evidence_id: str | None
    preview: str | None


@dataclass(frozen=True, slots=True)
class MemoryAnswer:
    answer: str
    mode_used: str
    confidence: str
    source_meeting_ids: tuple[str, ...]
    source_segment_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    evidence_chains: tuple[dict[str, object], ...]


@dataclass(frozen=True, slots=True)
class EngineHealth:
    status: str
    transcription: str
    embeddings: str
    local_llm: str
    detail: str


@dataclass(frozen=True, slots=True)
class EnginePreferencesSnapshot:
    language: str | None
    transcription_quality: str
    asr_provider: str
    asr_model: str
    embeddings_enabled: bool
    embedding_provider: str
    local_llm_provider: str
    diarization_enabled: bool
    retain_raw_audio: bool = False


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    total_meetings: int
    total_transcripts: int
    total_knowledge_nodes: int
    pending_reviews: int
    recent_meetings: tuple[MeetingSummary, ...]
