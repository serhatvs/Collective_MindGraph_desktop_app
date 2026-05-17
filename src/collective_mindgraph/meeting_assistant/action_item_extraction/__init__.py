"""Action item extraction service submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.meeting_assistant.models import ActionItem, TranscriptSegment


class ActionItemExtractor(Protocol):
    """Extracts tasks, assignments, and ownership hints from conversation text."""

    def extract(self, segments: tuple[TranscriptSegment, ...]) -> tuple[ActionItem, ...]:
        """Return action items grounded in transcript evidence."""
