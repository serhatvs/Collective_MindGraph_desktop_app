"""Structured insights extracted from meeting evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from .identifiers import EvidenceId, InsightId, MeetingId


class InsightKind(StrEnum):
    TASK = "task"
    DECISION = "decision"
    TOPIC = "topic"
    PERSON = "person"
    ENTITY = "entity"
    RISK = "risk"
    OPEN_QUESTION = "open_question"
    FOLLOW_UP = "follow_up"


class ReviewDecision(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class Insight:
    """A reviewable fact or action derived from a meeting."""

    id: InsightId
    meeting_id: MeetingId
    kind: InsightKind
    title: str
    body: str
    review: ReviewDecision
    created_at: datetime
    updated_at: datetime
    evidence_id: EvidenceId | None = None
    confidence: float | None = None
    edited_by_user: bool = False
    needs_review: bool = False
    attributes: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.title.strip() and not self.body.strip():
            raise ValueError("Insight title or body is required.")
