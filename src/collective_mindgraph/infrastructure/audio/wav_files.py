"""Audio slicing utilities shared across pipeline stages."""

from __future__ import annotations

import os
import tempfile
import wave
from pathlib import Path


def create_temporary_wav_path(target_dir: Path, *, prefix: str) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    handle, temp_path = tempfile.mkstemp(prefix=prefix, suffix=".wav", dir=target_dir)
    os.close(handle)
    return Path(temp_path)


def extract_wav_region(
    source_path: Path,
    start_seconds: float,
    end_seconds: float,
    target_dir: Path,
) -> Path:
    target_path = create_temporary_wav_path(target_dir, prefix="audio_region_")
    try:
        with wave.open(str(source_path), "rb") as reader:
            frame_rate = reader.getframerate()
            channels = reader.getnchannels()
            sample_width = reader.getsampwidth()
            total_frames = reader.getnframes()
            start_frame = max(0, min(total_frames, int(start_seconds * frame_rate)))
            end_frame = max(start_frame + 1, min(total_frames, int(end_seconds * frame_rate)))
            reader.setpos(start_frame)
            frames = reader.readframes(end_frame - start_frame)

        with wave.open(str(target_path), "wb") as writer:
            writer.setnchannels(channels)
            writer.setsampwidth(sample_width)
            writer.setframerate(frame_rate)
            writer.writeframes(frames)
        return target_path
    except Exception:
        target_path.unlink(missing_ok=True)
        raise


def wav_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        frame_rate = handle.getframerate()
        frame_count = handle.getnframes()
    return frame_count / frame_rate if frame_rate else 0.0
