"""Microphone array provider submodule."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AudioFrame:
    pcm: bytes
    sample_rate_hz: int
    channel_count: int
    timestamp_seconds: float


class AudioCaptureDevice(Protocol):
    """Provider boundary for laptop mics, room arrays, or embedded devices."""

    def frames(self) -> object:
        """Return an iterable or async iterable of audio frames."""
