"""Media normalization helpers built around ffmpeg."""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class NormalizedAudio:
    path: Path
    sample_rate: int
    channels: int
    duration_seconds: float


class FFmpegAudioNormalizer:
    def __init__(self, sample_rate: int, channels: int) -> None:
        self._sample_rate = sample_rate
        self._channels = channels

    def pcm_to_wav(
        self,
        pcm_bytes: bytes,
        target_path: Path,
        sample_width_bytes: int,
    ) -> NormalizedAudio:
        with wave.open(str(target_path), "wb") as handle:
            handle.setnchannels(self._channels)
            handle.setsampwidth(sample_width_bytes)
            handle.setframerate(self._sample_rate)
            handle.writeframes(pcm_bytes)
        return self.inspect_wav(target_path)

    @staticmethod
    def inspect_wav(path: Path) -> NormalizedAudio:
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            sample_rate = handle.getframerate()
            channels = handle.getnchannels()
        duration_seconds = frames / sample_rate if sample_rate else 0.0
        return NormalizedAudio(
            path=path,
            sample_rate=sample_rate,
            channels=channels,
            duration_seconds=duration_seconds,
        )
