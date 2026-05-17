"""Speech-to-text engine submodule."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from collective_mindgraph.meeting_assistant.models import TranscriptSegment


@dataclass(frozen=True, slots=True)
class TranscriptionRequest:
    audio_uri: str
    language: str | None = None
    enable_word_timestamps: bool = True


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    segments: tuple[TranscriptSegment, ...]
    provider_name: str


class SpeechToTextProvider(Protocol):
    """Provider boundary for local, cloud, or hybrid transcription engines."""

    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        """Convert audio into timestamped transcript segments."""
