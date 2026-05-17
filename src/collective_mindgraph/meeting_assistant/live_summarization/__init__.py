"""Live summarization service submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.meeting_assistant.models import MeetingSummary, TranscriptSegment


class LiveSummarizer(Protocol):
    """Produces incremental or final summaries from transcript segments."""

    def summarize(self, segments: tuple[TranscriptSegment, ...]) -> MeetingSummary:
        """Generate a grounded summary."""
