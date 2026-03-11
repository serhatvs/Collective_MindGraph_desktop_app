"""Audio slicing utilities shared across pipeline stages."""

from __future__ import annotations

import os
import tempfile
import wave
from pathlib import Path


def extract_wav_region(
    source_path: Path,
    start_seconds: float,
    end_seconds: float,
    target_dir: Path,
) -> Path:
    handle, temp_path = tempfile.mkstemp(prefix="audio_region_", suffix=".wav", dir=target_dir)
    os.close(handle)

    with wave.open(str(source_path), "rb") as reader:
        frame_rate = reader.getframerate()
        channels = reader.getnchannels()
        sample_width = reader.getsampwidth()
        total_frames = reader.getnframes()
        start_frame = max(0, min(total_frames, int(start_seconds * frame_rate)))
        end_frame = max(start_frame + 1, min(total_frames, int(end_seconds * frame_rate)))
        reader.setpos(start_frame)
        frames = reader.readframes(end_frame - start_frame)

    with wave.open(temp_path, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(sample_width)
        writer.setframerate(frame_rate)
        writer.writeframes(frames)

    return Path(temp_path)


def wav_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        frame_rate = handle.getframerate()
        frame_count = handle.getnframes()
    return frame_count / frame_rate if frame_rate else 0.0
