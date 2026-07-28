"""Typed memory search and grounded-answer transport models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MemoryEvidenceResponse(BaseModel):
    id: str
    meeting_id: int
    meeting_title: str
    segment_id: str | None = None
    text_preview: str | None = None
    start_seconds: float | None = None
    end_seconds: float | None = None


class MemorySearchItemResponse(BaseModel):
    node_id: str
    kind: str
    title: str
    body: str
    score: float
    matched_by: list[str] = Field(default_factory=list)
    evidence: MemoryEvidenceResponse | None = None


class MemorySearchResponse(BaseModel):
    query: str
    mode: str
    items: list[MemorySearchItemResponse] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    total: int
    next_cursor: str | None = None


class MemoryReasoningStepResponse(BaseModel):
    node_id: str
    kind: str
    title: str
    body: str
    relationship: str | None = None
    direction: str
    evidence_id: str | None = None


class MemorySentenceValidationResponse(BaseModel):
    sentence: str
    supported: bool
    citations: list[str] = Field(default_factory=list)
    unsupported_terms: list[str] = Field(default_factory=list)


class MemoryAnswerResponse(BaseModel):
    answer: str
    mode_requested: str
    mode_used: str
    validation_status: str
    confidence: str
    evidence_coverage: float
    sources: list[MemoryEvidenceResponse] = Field(default_factory=list)
    reasoning_steps: list[MemoryReasoningStepResponse] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    sentence_validations: list[MemorySentenceValidationResponse] = Field(default_factory=list)
