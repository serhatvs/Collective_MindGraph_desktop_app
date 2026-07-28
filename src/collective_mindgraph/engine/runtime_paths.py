"""Stable local storage paths owned by the engine."""

from __future__ import annotations

import os
from pathlib import Path

APP_DIRECTORY_NAME = "CollectiveMindGraph"
DATABASE_FILENAME = "collective_mindgraph.sqlite3"


def app_storage_directory() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data)
    elif os.name == "nt":
        base = Path.home() / "AppData" / "Local"
    else:
        base = Path.home() / ".local" / "share"
    return (base / APP_DIRECTORY_NAME).resolve()


def canonical_database_path() -> Path:
    configured = os.environ.get("CMG_DATABASE_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return app_storage_directory() / DATABASE_FILENAME
