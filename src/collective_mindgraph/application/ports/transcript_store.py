"""Transcript persistence port."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from collective_mindgraph.domain import MeetingId, SegmentId, Transcript, TranscriptSegment


class TranscriptStore(Protocol):
    def save(self, transcript: Transcript) -> Transcript: ...

    def get_by_conversation_id(self, conversation_id: str) -> Transcript | None: ...

    def latest_for_meeting(self, meeting_id: MeetingId) -> Transcript | None: ...

    def meeting_id_for_segment(self, segment_id: SegmentId) -> MeetingId | None: ...

    def update_segment_text(
        self,
        segment_id: SegmentId,
        *,
        corrected_text: str,
        now: datetime,
    ) -> TranscriptSegment | None: ...

    def count(self) -> int: ...
