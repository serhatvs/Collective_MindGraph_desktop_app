"""Typed identifiers shared by domain contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

ConversationId = NewType("ConversationId", str)
KnowledgeRecordId = NewType("KnowledgeRecordId", str)
OrganizationId = NewType("OrganizationId", str)
SpeakerId = NewType("SpeakerId", str)
UserId = NewType("UserId", str)
WorkspaceId = NewType("WorkspaceId", str)


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Pointer back to the evidence behind generated memory or answers."""

    origin: str
    external_id: str | None = None
    start_seconds: float | None = None
    end_seconds: float | None = None
