"""Speaker diarization submodule."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from collective_mindgraph.shared import SpeakerId


@dataclass(frozen=True, slots=True)
class SpeakerTurn:
    speaker_id: SpeakerId
    start_seconds: float
    end_seconds: float
    confidence: float | None = None


class SpeakerDiarizationProvider(Protocol):
    """Provider boundary for local or cloud speaker identification."""

    def identify_speakers(self, audio_uri: str) -> tuple[SpeakerTurn, ...]:
        """Return speaker turns for the supplied audio source."""
