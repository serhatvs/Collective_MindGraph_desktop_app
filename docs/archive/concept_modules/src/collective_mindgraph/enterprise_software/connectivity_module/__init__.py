"""Connectivity module provider submodule."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ProcessingSubmission:
    audio_uri: str
    metadata: dict[str, str]


class ProcessingTransport(Protocol):
    """Transport boundary for local, LAN, cloud, or offline queue delivery."""

    def submit_audio(self, submission: ProcessingSubmission) -> str:
        """Return an external processing job or conversation ID."""
