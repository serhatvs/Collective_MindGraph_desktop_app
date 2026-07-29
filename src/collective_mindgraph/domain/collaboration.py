"""Comments, mentions, and activity shared across a workspace."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from .identifiers import ActivityEventId, CommentId, DeviceId, SyncId, WorkspaceId

MAX_COMMENT_CHARACTERS = 5000
MENTION_PATTERN = re.compile(r"(?<![\w@])@([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")


class ActivityKind(StrEnum):
    """What happened, from the workspace's point of view."""

    MEETING_ADDED = "meeting.added"
    TRANSCRIPT_CORRECTED = "transcript.corrected"
    INSIGHT_REVIEWED = "insight.reviewed"
    COMMENT_ADDED = "comment.added"
    MEMBER_MENTIONED = "member.mentioned"
    TASK_ASSIGNED = "task.assigned"


@dataclass(frozen=True, slots=True)
class Comment:
    """One comment on a synchronized entity.

    Comments append. Two devices writing at once both keep their comment
    rather than one silently replacing the other, which is why comments never
    reach the conflict inbox.
    """

    id: CommentId
    workspace_id: WorkspaceId
    target_type: str
    target_sync_id: SyncId
    body: str
    author_subject: str
    created_at: datetime
    updated_at: datetime
    sync_id: SyncId | None = None
    parent_id: CommentId | None = None
    updated_by_device: DeviceId | None = None

    def __post_init__(self) -> None:
        _require_uuid(self.id, "Comment id")
        _require_uuid(self.workspace_id, "Workspace id")
        _require_uuid(self.target_sync_id, "Target id")
        if not self.target_type.strip():
            raise ValueError("Comment target type is required.")
        if not self.body.strip():
            raise ValueError("A comment cannot be empty.")
        if len(self.body) > MAX_COMMENT_CHARACTERS:
            raise ValueError(f"A comment may hold at most {MAX_COMMENT_CHARACTERS} characters.")
        if not self.author_subject.strip():
            raise ValueError("A comment needs an author.")
        for label, moment in (("Created", self.created_at), ("Updated", self.updated_at)):
            if moment.tzinfo is None:
                raise ValueError(f"{label} timestamp must be timezone-aware.")
        if self.parent_id is not None:
            _require_uuid(self.parent_id, "Parent comment id")

    @property
    def mentions(self) -> tuple[str, ...]:
        """Return the subjects this comment mentions, in order, without repeats."""

        return extract_mentions(self.body)

    @property
    def is_reply(self) -> bool:
        return self.parent_id is not None


@dataclass(frozen=True, slots=True)
class ActivityEvent:
    """One append-only record of something that happened."""

    id: ActivityEventId
    workspace_id: WorkspaceId
    kind: ActivityKind
    created_at: datetime
    actor_subject: str | None = None
    object_type: str | None = None
    object_sync_id: SyncId | None = None
    sync_id: SyncId | None = None
    details: dict[str, str] = field(default_factory=dict)
    updated_by_device: DeviceId | None = None

    def __post_init__(self) -> None:
        _require_uuid(self.id, "Activity id")
        _require_uuid(self.workspace_id, "Workspace id")
        if self.created_at.tzinfo is None:
            raise ValueError("Activity timestamp must be timezone-aware.")
        if self.object_sync_id is not None:
            _require_uuid(self.object_sync_id, "Activity object id")


def extract_mentions(body: str) -> tuple[str, ...]:
    """Return mentioned subjects in first-seen order.

    Mentions are plain `@address` text so that a comment stays readable, and
    resolution to a member happens against the workspace's own membership
    rather than anything the author typed.
    """

    seen: dict[str, None] = {}
    for match in MENTION_PATTERN.finditer(body):
        seen.setdefault(match.group(1).casefold(), None)
    return tuple(seen)


def _require_uuid(value: object, label: str) -> None:
    try:
        UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError(f"{label} must be a UUID.") from error


__all__ = [
    "MAX_COMMENT_CHARACTERS",
    "ActivityEvent",
    "ActivityKind",
    "Comment",
    "extract_mentions",
]
