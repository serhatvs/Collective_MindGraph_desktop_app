"""Domain models for Collective MindGraph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BranchType = Literal["root", "main", "side"]


@dataclass(frozen=True, slots=True)
class Session:
    id: int
    title: str
    device_id: str
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class Transcript:
    id: int
    session_id: int
    text: str
    confidence: float
    created_at: str


@dataclass(frozen=True, slots=True)
class GraphNode:
    id: int
    session_id: int
    transcript_id: int | None
    parent_node_id: int | None
    branch_type: BranchType
    branch_slot: int | None
    node_text: str
    override_reason: str | None
    created_at: str


@dataclass(frozen=True, slots=True)
class Snapshot:
    id: int
    session_id: int
    node_count: int
    hash_sha256: str
    created_at: str


@dataclass(frozen=True, slots=True)
class TranscriptTopic:
    label: str
    start: float
    end: float


@dataclass(frozen=True, slots=True)
class TranscriptSpeakerStat:
    speaker: str
    segment_count: int
    speaking_seconds: float
    overlap_segments: int
    first_start: float
    last_end: float


@dataclass(frozen=True, slots=True)
class TranscriptAnalysisSegment:
    segment_id: str
    start: float
    end: float
    speaker: str
    raw_text: str
    corrected_text: str
    confidence: float | None
    speaker_confidence: float | None
    overlap: bool
    notes: list[str]


@dataclass(frozen=True, slots=True)
class TranscriptQualityReport:
    segment_count: int
    speaker_count: int
    unresolved_segments: int
    overlap_ratio: float
    avg_asr_confidence: float | None
    avg_speaker_confidence: float | None
    word_timing_coverage: float
    corrected_change_ratio: float
    topic_count: int
    action_item_count: int
    decision_count: int
    question_count: int
    summary_present: bool
    warnings: list[str]


@dataclass(frozen=True, slots=True)
class TranscriptAnalysis:
    transcript_id: int
    source_provider: str
    backend_conversation_id: str | None
    raw_text_output: str
    corrected_text_output: str
    summary: str | None
    topics: list[TranscriptTopic]
    action_items: list[str]
    decisions: list[str]
    speaker_stats: list[TranscriptSpeakerStat]
    segments: list[TranscriptAnalysisSegment]
    quality_report: TranscriptQualityReport | None
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class SessionDetail:
    session: Session
    transcripts: list[Transcript]
    graph_nodes: list[GraphNode]
    snapshots: list[Snapshot]
    transcript_analyses: dict[int, TranscriptAnalysis]


@dataclass(frozen=True, slots=True)
class AppSummary:
    total_sessions: int
    active_sessions: int
    total_transcripts: int
    total_nodes: int
    total_snapshots: int


@dataclass(frozen=True, slots=True)
class TranscriptDraft:
    text: str
    confidence: float
    created_at: str


@dataclass(frozen=True, slots=True)
class TranscriptAnalysisDraft:
    source_provider: str
    backend_conversation_id: str | None
    raw_text_output: str
    corrected_text_output: str
    summary: str | None
    topics: list[TranscriptTopic]
    action_items: list[str]
    decisions: list[str]
    speaker_stats: list[TranscriptSpeakerStat]
    segments: list[TranscriptAnalysisSegment]
    quality_report: TranscriptQualityReport | None
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class GraphNodeDraft:
    transcript_id: int | None
    parent_node_id: int | None
    branch_type: BranchType
    branch_slot: int | None
    node_text: str
    override_reason: str | None
    created_at: str
