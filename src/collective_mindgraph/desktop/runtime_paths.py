"""Runtime path helpers for source and frozen desktop builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "CollectiveMindGraph"


def is_frozen_build() -> bool:
    return bool(getattr(sys, "frozen", False))


def executable_dir() -> Path:
    if is_frozen_build():
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


def app_storage_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base_dir = Path(local_app_data)
    elif os.name == "nt":
        base_dir = Path.home() / "AppData" / "Local"
    else:
        base_dir = Path.home() / ".local" / "share"
    return (base_dir / APP_DIR_NAME).resolve()


def default_recordings_dir() -> Path:
    return app_storage_dir() / "recordings"


def default_transcription_settings_path() -> Path:
    if is_frozen_build():
        return app_storage_dir() / "transcription_settings.json"
    return (Path.cwd() / "transcription_settings.json").resolve()


def embedded_engine_temp_dir() -> Path:
    return app_storage_dir() / "temp"


def wake_phrase_model_candidates() -> list[Path]:
    candidates: list[Path] = []
    roots = [executable_dir()]
    if is_frozen_build():
        roots.append(app_storage_dir())
    for root in roots:
        candidates.extend(
            [
                root / "wake_phrase_models" / "vosk-model-small-en-us-0.15",
                root / "wake_phrase_models" / "vosk-model-en-us-0.22",
                root / "models" / "vosk-model-small-en-us-0.15",
                root / "models" / "vosk-model-en-us-0.22",
            ]
        )
    return candidates
