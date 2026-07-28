"""Knowledge graph entities and evidence links."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from .identifiers import EdgeId, EvidenceId, KnowledgeNodeId, MeetingId, SegmentId


class KnowledgeNodeKind(StrEnum):
    MEETING = "meeting"
    SEGMENT = "segment"
    NOTE = "note"
    TASK = "task"
    DECISION = "decision"
    TOPIC = "topic"
    PERSON = "person"
    DOCUMENT = "document"
    PROJECT = "project"
    ENTITY = "entity"
    RISK = "risk"
    OPEN_QUESTION = "open_question"
    FOLLOW_UP = "follow_up"


class RelationshipKind(StrEnum):
    CONTAINS = "contains"
    MENTIONS = "mentions"
    CREATES = "creates"
    SUPPORTS = "supports"
    ASSIGNED_TO = "assigned_to"
    RELATED_TO = "related_to"
    DERIVED_FROM = "derived_from"
    MERGED_INTO = "merged_into"


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    """Traceable pointer from derived knowledge to source material."""

    id: EvidenceId
    meeting_id: MeetingId
    created_at: datetime
    segment_id: SegmentId | None = None
    start_seconds: float | None = None
    end_seconds: float | None = None
    text_preview: str | None = None
    confidence: float | None = None
    extractor: str | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeNode:
    id: KnowledgeNodeId
    kind: KnowledgeNodeKind
    title: str
    body: str
    created_at: datetime
    updated_at: datetime
    meeting_id: MeetingId | None = None
    evidence_id: EvidenceId | None = None
    attributes: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class KnowledgeEdge:
    id: EdgeId
    source_id: KnowledgeNodeId
    target_id: KnowledgeNodeId
    kind: RelationshipKind
    created_at: datetime
    evidence_id: EvidenceId | None = None
    confidence: float = 1.0
    attributes: dict[str, object] = field(default_factory=dict)
