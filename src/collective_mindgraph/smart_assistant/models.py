"""Assistant query, answer, and attribution model group."""

from __future__ import annotations

from dataclasses import dataclass

from collective_mindgraph.shared import OrganizationId, SourceReference, UserId


@dataclass(frozen=True, slots=True)
class AssistantQuery:
    organization_id: OrganizationId
    text: str
    user_id: UserId | None = None
    conversation_context: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AssistantSource:
    title: str
    reference: SourceReference
    relevance: float | None = None


@dataclass(frozen=True, slots=True)
class AssistantAnswer:
    text: str
    sources: tuple[AssistantSource, ...] = ()
    confidence: float | None = None
    ambiguity_warnings: tuple[str, ...] = ()
