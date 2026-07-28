from __future__ import annotations

from pydantic import BaseModel, Field

from collective_mindgraph.application.transcription.contracts import EvidenceChain


class SentenceValidation(BaseModel):
    sentence: str
    supported: bool
    sources: list[str] = Field(default_factory=list)
    unsupported_terms: list[str] = Field(default_factory=list)


class MemoryAskResponse(BaseModel):
    query: str
    mode: str
    mode_requested: str | None = None
    mode_used: str | None = None  # "evidence_only" | "llm_assisted" | "evidence_only_fallback"
    answer_type: str  # Legacy field, mapping to mode_used
    answer_validation_status: str  # "accepted", "rejected_unsupported_terms", "rejected_missing_sources", "fallback_to_evidence_only"
    short_answer: str
    evidence_chains: list[EvidenceChain] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence_level: str  # "high", "medium", "low", "insufficient"
    evidence_coverage_score: float = 0.0
    source_session_ids: list[str] = Field(default_factory=list)
    source_segment_ids: list[str] = Field(default_factory=list)
    used_sources: list[str] = Field(default_factory=list)
    rejected_sources: list[str] = Field(default_factory=list)
    sentence_validations: list[SentenceValidation] = Field(default_factory=list)
    missing_evidence_note: str | None = None
    rejected_terms: list[str] = Field(default_factory=list)
