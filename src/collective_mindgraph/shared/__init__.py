"""Shared kernel primitives used across V2 domains."""

from .events import DomainEvent
from .ids import (
    ConversationId,
    KnowledgeRecordId,
    OrganizationId,
    SourceReference,
    SpeakerId,
    UserId,
    WorkspaceId,
)

__all__ = [
    "ConversationId",
    "DomainEvent",
    "KnowledgeRecordId",
    "OrganizationId",
    "SourceReference",
    "SpeakerId",
    "UserId",
    "WorkspaceId",
]
