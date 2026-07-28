"""Reproducibility metadata for transcription experiments."""

from __future__ import annotations

import importlib.metadata
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any


def current_git_commit(_path: Path | None = None) -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def environment_information() -> dict[str, Any]:
    packages: dict[str, str | None] = {}
    for package in ("faster-whisper", "ctranslate2", "PySide6"):
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = None
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": packages,
    }
