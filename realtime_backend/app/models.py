"""Pydantic models shared across the realtime transcription backend."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class SpeechRegion(BaseModel):
    start: float
    end: float
    confidence: float | None = None


class WordTimestamp(BaseModel):
    start: float | None = None
    end: float | None = None
    word: str
    probability: float | None = None


class ASRSegment(BaseModel):
    start: float
    end: float
    text: str
    confidence: float | None = None
    words: list[WordTimestamp] = Field(default_factory=list)


class DiarizationTurn(BaseModel):
    start: float
    end: float
    speaker: str
    confidence: float | None = None
    overlap: bool = False


class TranscriptSegment(BaseModel):
    segment_id: str
    start: float
    end: float
    speaker: str
    raw_text: str
    corrected_text: str
    words: list[WordTimestamp] = Field(default_factory=list)
    confidence: float | None = None
    speaker_confidence: float | None = None
    overlap: bool = False
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TopicSegment(BaseModel):
    label: str
    start: float
    end: float


class ProcessingDebug(BaseModel):
    vad_regions: list[SpeechRegion] = Field(default_factory=list)
    diarization_turns: list[DiarizationTurn] = Field(default_factory=list)
    asr_segments: list[ASRSegment] = Field(default_factory=list)


class ConversationTranscript(BaseModel):
    conversation_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    source: str
    language: str | None = None
    status: str = "completed"
    segments: list[TranscriptSegment] = Field(default_factory=list)
    summary: str | None = None
    topics: list[TopicSegment] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    debug: ProcessingDebug | None = None


class CorrectionRequest(BaseModel):
    conversation_id: str
    language: str | None = None
    context_segments: list[TranscriptSegment] = Field(default_factory=list)
    segments: list[TranscriptSegment]


class CorrectionResult(BaseModel):
    segment_id: str
    corrected_text: str
    speaker_override: str | None = None
    notes: list[str] = Field(default_factory=list)
    confidence_note: str | None = None


class SpeakerStats(BaseModel):
    speaker: str
    segment_count: int
    speaking_seconds: float
    overlap_segments: int = 0
    first_start: float
    last_end: float


class TranscriptRenderings(BaseModel):
    raw_text_output: str
    corrected_text_output: str


class HealthResponse(BaseModel):
    status: str
    app_name: str
    vad_provider: str
    asr_provider: str
    asr_provider_resolved: str | None = None
    asr_fallback_provider: str | None = None
    diarizer_provider: str
    llm_provider: str
    llm_provider_resolved: str | None = None
    llm_fallback_provider: str | None = None


class FileTranscriptionResponse(BaseModel):
    transcript: ConversationTranscript
    text_output: str
    raw_text_output: str
    corrected_text_output: str
    speaker_stats: list[SpeakerStats] = Field(default_factory=list)


class TranscriptResponse(BaseModel):
    transcript: ConversationTranscript
    renderings: TranscriptRenderings
    speaker_stats: list[SpeakerStats] = Field(default_factory=list)


class SummaryResponse(BaseModel):
    conversation_id: str
    summary: str | None = None
    topics: list[TopicSegment] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)


class QualityComparison(BaseModel):
    text_overlap: float | None = None
    speaker_match_ratio: float | None = None
    action_item_overlap: float | None = None
    summary_overlap: float | None = None


class QualityReport(BaseModel):
    conversation_id: str
    segment_count: int
    speaker_count: int
    unresolved_segments: int
    overlap_ratio: float
    avg_asr_confidence: float | None = None
    avg_speaker_confidence: float | None = None
    word_timing_coverage: float
    corrected_change_ratio: float
    topic_count: int
    action_item_count: int
    decision_count: int
    question_count: int
    summary_present: bool
    comparison: QualityComparison | None = None
    warnings: list[str] = Field(default_factory=list)
