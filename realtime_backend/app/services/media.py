"""Media normalization helpers built around ffmpeg."""

from __future__ import annotations

import os
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path
import sys


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

    def normalize_to_wav(self, source_path: Path, target_path: Path) -> NormalizedAudio:
        command = [
            _ffmpeg_executable(),
            "-y",
            "-i",
            str(source_path),
            "-vn",
            "-ac",
            str(self._channels),
            "-ar",
            str(self._sample_rate),
            "-f",
            "wav",
            str(target_path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError(
                "ffmpeg normalization failed. Ensure ffmpeg is installed and on PATH.\n"
                f"{completed.stderr.strip()}"
            )
        return self.inspect_wav(target_path)

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


def _ffmpeg_executable() -> str:
    env_value = (os.getenv("CMG_RT_FFMPEG_PATH") or os.getenv("CMG_FFMPEG_EXE") or "").strip()
    if env_value:
        return env_value

    if getattr(sys, "frozen", False):
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        executable_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
        candidate = bundle_root / executable_name
        if candidate.exists():
            return str(candidate)

    return "ffmpeg"
