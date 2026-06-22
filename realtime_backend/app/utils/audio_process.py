"""Audio preprocessing and normalization helpers."""

from __future__ import annotations

import logging
import os
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AudioInspection:
    sample_rate: int
    channels: int
    sample_width_bytes: int
    frame_count: int
    duration_seconds: float
    format: str


def _resolve_ffmpeg_executable() -> str:
    """Return the ffmpeg executable path.

    Reads CMG_RT_FFMPEG_PATH or CMG_FFMPEG_EXE env vars first (same as
    media.py), then falls back to 'ffmpeg' on the system PATH.
    """
    env_value = (os.getenv("CMG_RT_FFMPEG_PATH") or os.getenv("CMG_FFMPEG_EXE") or "").strip()
    if env_value:
        return env_value
    return "ffmpeg"


def normalize_audio(source_path: Path, target_path: Path, sample_rate: int = 16000) -> bool:
    """
    Normalize audio file to standard PCM format using ffmpeg.
    Logs parameters and timing for quality auditing.
    """
    ffmpeg_exe = _resolve_ffmpeg_executable()
    LOGGER.info("Preprocessing audio: %s -> %s (SR: %d)", source_path.name, target_path.name, sample_rate)

    command = [
        ffmpeg_exe,
        "-y",
        "-i", str(source_path),
        "-ar", str(sample_rate),
        "-ac", "1",
        "-sample_fmt", "s16",
        str(target_path)
    ]

    try:
        # Run ffmpeg and capture stderr for quality logs
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        if result.stderr:
            LOGGER.debug("ffmpeg output: %s", result.stderr)
        return True
    except subprocess.CalledProcessError as exc:
        LOGGER.error("ffmpeg normalization failed: %s", exc.stderr)
        return False
    except FileNotFoundError:
        LOGGER.error("ffmpeg not found at '%s'. Audio normalization skipped.", ffmpeg_exe)
        return False


def inspect_audio(path: Path) -> AudioInspection | None:
    """Return WAV container facts for diagnostics, or None if the file is unreadable."""
    try:
        with wave.open(str(path), "rb") as handle:
            sample_rate = handle.getframerate()
            channels = handle.getnchannels()
            sample_width = handle.getsampwidth()
            frame_count = handle.getnframes()
    except (wave.Error, OSError) as exc:
        LOGGER.warning("Audio inspection failed for %s: %s", path, exc)
        return None

    duration = frame_count / sample_rate if sample_rate else 0.0
    return AudioInspection(
        sample_rate=sample_rate,
        channels=channels,
        sample_width_bytes=sample_width,
        frame_count=frame_count,
        duration_seconds=duration,
        format="wav",
    )
