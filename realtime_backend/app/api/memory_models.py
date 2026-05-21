from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from ..models import EvidenceChain

class SentenceValidation(BaseModel):
    sentence: str
    supported: bool
    sources: List[str] = Field(default_factory=list)
    unsupported_terms: List[str] = Field(default_factory=list)

class MemoryAskResponse(BaseModel):
    query: str
    mode: str
    mode_requested: str | None = None
    mode_used: str | None = None  # "evidence_only" | "llm_assisted" | "evidence_only_fallback"
    answer_type: str  # Legacy field, mapping to mode_used
    answer_validation_status: str  # "accepted", "rejected_unsupported_terms", "rejected_missing_sources", "fallback_to_evidence_only"
    short_answer: str
    evidence_chains: List[EvidenceChain] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    confidence_level: str  # "high", "medium", "low", "insufficient"
    evidence_coverage_score: float = 0.0
    source_session_ids: List[str] = Field(default_factory=list)
    source_segment_ids: List[str] = Field(default_factory=list)
    used_sources: List[str] = Field(default_factory=list)
    rejected_sources: List[str] = Field(default_factory=list)
    sentence_validations: List[SentenceValidation] = Field(default_factory=list)
    missing_evidence_note: Optional[str] = None
    rejected_terms: List[str] = Field(default_factory=list)

