"""Shared test isolation for the automated suite."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from collective_mindgraph.engine.runtime_paths import (
    DATABASE_FILENAME,
    app_storage_directory,
    canonical_database_path,
)


@pytest.fixture(scope="session", autouse=True)
def isolated_application_storage(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Keep every test away from the installed application's real storage.

    ``EngineSettings`` resolves its database and data directory from the
    operating system's per-user application storage. Any test that builds
    settings without overriding those paths would otherwise read and write the
    developer's installed database.
    """

    root = tmp_path_factory.mktemp("application-storage")
    previous = {
        name: os.environ.get(name) for name in ("CMG_DATABASE_PATH", "LOCALAPPDATA", "HOME")
    }
    os.environ["CMG_DATABASE_PATH"] = str(root / DATABASE_FILENAME)
    os.environ["LOCALAPPDATA"] = str(root)
    if os.name != "nt":
        os.environ["HOME"] = str(root)
    resolved = root.resolve()
    if canonical_database_path().parent != resolved or not app_storage_directory().is_relative_to(
        resolved
    ):
        raise RuntimeError("Test isolation failed to redirect application storage.")
    try:
        yield root
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
