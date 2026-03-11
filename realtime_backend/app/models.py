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
    metadata: dict[str, Any] = Field(default_factory=dict)
    debug: ProcessingDebug | None = None


class CorrectionRequest(BaseModel):
    conversation_id: str
    language: str | None = None
    segments: list[TranscriptSegment]


class CorrectionResult(BaseModel):
    segment_id: str
    corrected_text: str
    speaker_override: str | None = None
    notes: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    app_name: str
    vad_provider: str
    asr_provider: str
    diarizer_provider: str
    llm_provider: str


class FileTranscriptionResponse(BaseModel):
    transcript: ConversationTranscript
    text_output: str


class SummaryResponse(BaseModel):
    conversation_id: str
    summary: str | None = None
    topics: list[TopicSegment] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
