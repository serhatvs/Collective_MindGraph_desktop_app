"""Transport schemas for review and knowledge exploration."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class InsightResponse(BaseModel):
    id: str
    meeting_id: int
    kind: str
    title: str
    body: str
    review: str
    evidence_id: str | None = None
    confidence: float | None = None
    edited_by_user: bool
    needs_review: bool
    created_at: datetime
    updated_at: datetime


class InsightPageResponse(BaseModel):
    items: list[InsightResponse] = Field(default_factory=list)
    total: int
    next_cursor: str | None = None


class ReviewInsightRequest(BaseModel):
    decision: str
    title: str | None = None
    body: str | None = None


class KnowledgeNodeResponse(BaseModel):
    id: str
    meeting_id: int | None = None
    kind: str
    title: str
    body: str
    evidence_id: str | None = None
    attributes: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class KnowledgeNodePageResponse(BaseModel):
    items: list[KnowledgeNodeResponse] = Field(default_factory=list)
    total: int
    next_cursor: str | None = None


class KnowledgeEdgeResponse(BaseModel):
    id: str
    source_id: str
    target_id: str
    kind: str
    evidence_id: str | None = None
    confidence: float
    attributes: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class KnowledgeEdgePageResponse(BaseModel):
    items: list[KnowledgeEdgeResponse] = Field(default_factory=list)
    total: int
    next_cursor: str | None = None


class EvidenceResponse(BaseModel):
    id: str
    meeting_id: int
    segment_id: str | None = None
    start_seconds: float | None = None
    end_seconds: float | None = None
    text_preview: str | None = None
    confidence: float | None = None
    extractor: str | None = None
    created_at: datetime


class EvidencePageResponse(BaseModel):
    items: list[EvidenceResponse] = Field(default_factory=list)
    total: int
    next_cursor: str | None = None
