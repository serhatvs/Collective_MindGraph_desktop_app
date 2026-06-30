"""Pydantic models shared across the realtime transcription backend."""

from __future__ import annotations

from abc import ABC, abstractmethod
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
    raw_text: str = ""
    corrected_text: str = ""
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


class TaskItem(BaseModel):
    title: str
    responsible_person: str | None = None
    due_date_reference: str | None = None
    source_segment_id: str | None = None
    confidence_note: str | None = None


class DecisionItem(BaseModel):
    decision: str
    reason_context: str | None = None
    source_segment_id: str | None = None
    confidence_note: str | None = None


class ProcessingDebug(BaseModel):
    vad_regions: list[SpeechRegion] = Field(default_factory=list)
    diarization_turns: list[DiarizationTurn] = Field(default_factory=list)
    asr_segments: list[ASRSegment] = Field(default_factory=list)


class TranscriptionDiagnostics(BaseModel):
    provider: str
    model: str
    asr_status: str | None = None
    mock_fallback_used: bool = False
    runtime_profile: str | None = None
    device: str | None = None
    language: str | None = None
    quality_mode: str | None = None
    quality_profile: str | None = None
    beam_size: int | None = None
    compute_type: str | None = None
    word_timestamps_enabled: bool | None = None
    internal_vad_enabled: bool | None = None
    condition_on_previous_text: bool | None = None
    preprocessing_status: str | None = None
    preprocessing_format: str | None = None
    audio_duration: float
    sample_rate_in: int | None = None
    sample_rate_out: int | None = None
    channels_in: int | None = None
    channels_out: int | None = None
    rms_before: float | None = None
    rms_after: float | None = None
    vad_settings: dict[str, Any] = Field(default_factory=dict)
    chunk_count: int | None = None
    processing_time_seconds: float | None = None
    gpu_requested: bool | None = None
    gpu_loaded: bool | None = None
    gpu_fallback_happened: bool | None = None
    gpu_fallback_reason: str | None = None
    faster_whisper_cuda_load_status: str | None = None
    raw_transcript_length: int | None = None
    cleaned_transcript_length: int | None = None
    warnings: list[str] = Field(default_factory=list)


class QueryResultItem(BaseModel):
    result_type: str  # "transcript" | "task" | "decision" | "topic"
    text: str
    source_session_id: str
    source_segment_id: str | None = None
    source_reference_id: str | None = None
    matched_field: str | None = None
    matched_terms: list[str] = Field(default_factory=list)
    score: float = 1.0
    preview: str | None = None
    timestamp: str | None = None
    matched_by: str | None = None
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    edge_path: str | None = None
    node_id: str | None = None
    text_preview: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    graph_distance: int | None = None
    related_node_id: str | None = None
    edge_type: str | None = None


class QueryResponse(BaseModel):
    query: str
    results: list[QueryResultItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

class EvidenceStep(BaseModel):
    node_id: str
    node_type: str
    text: str
    edge_type: str | None = None
    direction: str = "out"
    source_reference_id: str | None = None
    source_session_id: str | None = None
    source_segment_id: str | None = None
    text_preview: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    edge_path: list[str] = Field(default_factory=list)

class EvidenceChain(BaseModel):
    steps: list[EvidenceStep] = Field(default_factory=list)
    explanation: str = ""

class ReasoningResponse(BaseModel):
    query: str
    answer_type: str = "graph_evidence"
    chains: list[EvidenceChain] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# Future Semantic/Vector Interfaces (Placeholders)
class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        raise NotImplementedError


class VectorStore(ABC):
    @abstractmethod
    async def add(self, id: str, vector: list[float], metadata: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def search(self, vector: list[float], limit: int = 5) -> list[dict[str, Any]]:
        raise NotImplementedError


class ConversationTranscript(BaseModel):
    conversation_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    source: str
    language: str | None = None
    quality_mode: str | None = None
    status: str = "completed"
    segments: list[TranscriptSegment] = Field(default_factory=list)
    summary: str | None = None
    topics: list[TopicSegment] = Field(default_factory=list)
    action_items: list[TaskItem] = Field(default_factory=list)
    decisions: list[DecisionItem] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    debug: ProcessingDebug | None = None
    diagnostics: TranscriptionDiagnostics | None = None


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
    asr_status: str | None = None
    asr_mock_fallback_used: bool = False
    asr_model_name: str | None = None
    asr_quality_profile: str | None = None
    asr_runtime_profile: str | None = None
    asr_device: str | None = None
    asr_compute_type: str | None = None
    asr_language: str | None = None
    gpu_enabled: bool | None = None
    gpu_required: bool | None = None
    cuda_available_through_torch: bool | None = None
    gpu_requested: bool | None = None
    gpu_actually_used_by_asr: bool | None = None
    faster_whisper_cuda_load_status: str | None = None
    gpu_fallback_happened: bool | None = None
    gpu_fallback_reason: str | None = None
    embedding_device: str | None = None
    local_llm_enabled: bool | None = None
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
    asr_status: str | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TranscriptResponse(BaseModel):
    transcript: ConversationTranscript
    renderings: TranscriptRenderings
    speaker_stats: list[SpeakerStats] = Field(default_factory=list)
    asr_status: str | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SummaryResponse(BaseModel):
    conversation_id: str
    summary: str | None = None
    topics: list[TopicSegment] = Field(default_factory=list)
    action_items: list[TaskItem] = Field(default_factory=list)
    decisions: list[DecisionItem] = Field(default_factory=list)


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
