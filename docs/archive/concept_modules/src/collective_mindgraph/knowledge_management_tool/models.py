"""Organizational knowledge model group."""

from __future__ import annotations

from dataclasses import dataclass

from collective_mindgraph.shared import KnowledgeRecordId, OrganizationId, SourceReference


@dataclass(frozen=True, slots=True)
class KnowledgeTag:
    name: str
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeRecord:
    record_id: KnowledgeRecordId
    organization_id: OrganizationId
    title: str
    body: str
    tags: tuple[KnowledgeTag, ...] = ()
    sources: tuple[SourceReference, ...] = ()


@dataclass(frozen=True, slots=True)
class KnowledgeLink:
    source_id: KnowledgeRecordId
    target_id: KnowledgeRecordId
    relationship: str
    confidence: float | None = None
