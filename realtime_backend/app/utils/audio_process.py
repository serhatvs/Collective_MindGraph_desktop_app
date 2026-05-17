"""Audio preprocessing and normalization helpers."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

LOGGER = logging.getLogger(__name__)

def normalize_audio(source_path: Path, target_path: Path, sample_rate: int = 16000) -> bool:
    """
    Normalize audio file to standard PCM format using ffmpeg.
    Logs parameters and timing for quality auditing.
    """
    LOGGER.info("Preprocessing audio: %s -> %s (SR: %d)", source_path.name, target_path.name, sample_rate)
    
    command = [
        "ffmpeg",
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
        LOGGER.error("ffmpeg not found in PATH. Audio normalization skipped.")
        return False
