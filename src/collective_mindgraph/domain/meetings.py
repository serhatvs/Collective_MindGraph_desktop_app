"""Meeting aggregate and lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .identifiers import MeetingId


class MeetingStatus(StrEnum):
    """User-meaningful lifecycle of a meeting."""

    DRAFT = "draft"
    RECORDING = "recording"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class Meeting:
    """A captured or imported meeting and its lifecycle metadata."""

    id: MeetingId
    title: str
    status: MeetingStatus
    created_at: datetime
    updated_at: datetime
    input_device: str | None = None

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("Meeting title is required.")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("Meeting timestamps must be timezone-aware.")
