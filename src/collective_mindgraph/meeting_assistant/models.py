"""Meeting intelligence model group."""

from __future__ import annotations

from dataclasses import dataclass, field

from collective_mindgraph.shared import ConversationId, SourceReference, SpeakerId


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    conversation_id: ConversationId
    text: str
    start_seconds: float
    end_seconds: float
    speaker_id: SpeakerId | None = None
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class MeetingSummary:
    conversation_id: ConversationId
    text: str
    sources: tuple[SourceReference, ...] = ()


@dataclass(frozen=True, slots=True)
class ActionItem:
    conversation_id: ConversationId
    text: str
    assignee: str | None = None
    due_hint: str | None = None
    sources: tuple[SourceReference, ...] = ()


@dataclass(frozen=True, slots=True)
class Decision:
    conversation_id: ConversationId
    text: str
    sources: tuple[SourceReference, ...] = field(default_factory=tuple)
