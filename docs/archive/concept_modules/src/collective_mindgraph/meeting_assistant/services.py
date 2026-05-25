"""Public service boundary for meeting intelligence workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import ActionItem, Decision, MeetingSummary, TranscriptSegment


@dataclass(frozen=True, slots=True)
class MeetingAnalysis:
    transcript: tuple[TranscriptSegment, ...]
    summary: MeetingSummary | None = None
    action_items: tuple[ActionItem, ...] = ()
    decisions: tuple[Decision, ...] = ()


class MeetingAssistantService(Protocol):
    """Coordinates meeting providers without exposing provider implementations."""

    def analyze_audio(self, audio_uri: str) -> MeetingAnalysis:
        """Transcribe and analyze one captured audio source."""

    def answer_meeting_question(self, conversation_id: str, question: str) -> str:
        """Answer a meeting-scoped question using grounded conversation context."""
