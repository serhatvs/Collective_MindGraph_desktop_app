"""Meeting lifecycle use cases."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from collective_mindgraph.domain import Meeting, MeetingId, MeetingStatus

from .pagination import Page, PageRequest
from .ports import MeetingStore

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


class CreateMeeting:
    def __init__(self, meetings: MeetingStore, clock: Clock = utc_now) -> None:
        self._meetings = meetings
        self._clock = clock

    def __call__(self, title: str, input_device: str | None = None) -> Meeting:
        cleaned_title = title.strip()
        if not cleaned_title:
            raise ValueError("Meeting title is required.")
        cleaned_device = input_device.strip() if input_device else None
        return self._meetings.create(
            title=cleaned_title,
            status=MeetingStatus.DRAFT,
            input_device=cleaned_device or None,
            now=self._clock(),
        )


class GetMeeting:
    def __init__(self, meetings: MeetingStore) -> None:
        self._meetings = meetings

    def __call__(self, meeting_id: MeetingId) -> Meeting | None:
        return self._meetings.get(meeting_id)


class ListMeetings:
    def __init__(self, meetings: MeetingStore) -> None:
        self._meetings = meetings

    def __call__(self, request: PageRequest, *, query: str = "") -> Page[Meeting]:
        return self._meetings.list(request, query=query.strip())


class RenameMeeting:
    def __init__(self, meetings: MeetingStore, clock: Clock = utc_now) -> None:
        self._meetings = meetings
        self._clock = clock

    def __call__(self, meeting_id: MeetingId, title: str) -> Meeting | None:
        cleaned_title = title.strip()
        if not cleaned_title:
            raise ValueError("Meeting title is required.")
        return self._meetings.rename(meeting_id, title=cleaned_title, now=self._clock())


class ArchiveMeeting:
    def __init__(self, meetings: MeetingStore, clock: Clock = utc_now) -> None:
        self._meetings = meetings
        self._clock = clock

    def __call__(self, meeting_id: MeetingId) -> Meeting | None:
        return self._meetings.set_status(
            meeting_id,
            status=MeetingStatus.ARCHIVED,
            now=self._clock(),
        )


class DeleteMeeting:
    def __init__(self, meetings: MeetingStore) -> None:
        self._meetings = meetings

    def __call__(self, meeting_id: MeetingId) -> bool:
        return self._meetings.delete(meeting_id)
