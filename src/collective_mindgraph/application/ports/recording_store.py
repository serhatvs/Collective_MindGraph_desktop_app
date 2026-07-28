"""Recording persistence port."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from collective_mindgraph.domain import (
    MeetingId,
    Recording,
    RecordingId,
    RecordingStorageStatus,
)


class RecordingStore(Protocol):
    def save(self, recording: Recording) -> None: ...

    def get(self, recording_id: RecordingId) -> Recording | None: ...

    def list_for_meeting(self, meeting_id: MeetingId) -> tuple[Recording, ...]: ...

    def update_storage(
        self,
        recording_id: RecordingId,
        *,
        status: RecordingStorageStatus,
        deleted_at: datetime | None = None,
    ) -> Recording | None: ...
