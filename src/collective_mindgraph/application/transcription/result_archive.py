"""Persistence boundary for processed transcription results."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from collective_mindgraph.domain import MeetingId, RecordingId

from .contracts import ConversationTranscript


class TranscriptionResultArchive(Protocol):
    def save(
        self,
        result: ConversationTranscript,
        *,
        meeting_id: MeetingId | None = None,
        source_path: Path | None = None,
        source_uri: str | None = None,
        recording_id: RecordingId | None = None,
    ) -> MeetingId: ...

    def get(self, conversation_id: str) -> ConversationTranscript | None: ...
