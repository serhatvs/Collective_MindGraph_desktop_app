"""Meeting persistence port."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from collective_mindgraph.application.pagination import Page, PageRequest
from collective_mindgraph.domain import Meeting, MeetingId, MeetingStatus


class MeetingStore(Protocol):
    def create(
        self,
        *,
        title: str,
        status: MeetingStatus,
        input_device: str | None,
        now: datetime,
    ) -> Meeting: ...

    def get(self, meeting_id: MeetingId) -> Meeting | None: ...

    def list(self, request: PageRequest, *, query: str = "") -> Page[Meeting]: ...

    def rename(self, meeting_id: MeetingId, *, title: str, now: datetime) -> Meeting | None: ...

    def set_status(
        self,
        meeting_id: MeetingId,
        *,
        status: MeetingStatus,
        now: datetime,
    ) -> Meeting | None: ...

    def delete(self, meeting_id: MeetingId) -> bool: ...

    def count(self) -> int: ...
