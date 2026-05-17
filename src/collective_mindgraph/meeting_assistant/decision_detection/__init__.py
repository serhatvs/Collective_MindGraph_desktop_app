"""Decision detection service submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.meeting_assistant.models import Decision, TranscriptSegment


class DecisionDetector(Protocol):
    """Finds explicit and implied decisions in a conversation."""

    def detect(self, segments: tuple[TranscriptSegment, ...]) -> tuple[Decision, ...]:
        """Return decisions grounded in transcript evidence."""
