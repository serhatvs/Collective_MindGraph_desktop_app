from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def test_package_and_app_factory_import_without_runtime_side_effects(tmp_path):
    local_app_data = tmp_path / "local-app-data"
    environment = {**os.environ, "LOCALAPPDATA": str(local_app_data)}
    script = """
import json
from pathlib import Path
import collective_mindgraph
from collective_mindgraph.engine.main import app, create_app
print(json.dumps({
    "title": app.title,
    "factory_title": create_app().title,
    "storage_exists": (Path(__import__("os").environ["LOCALAPPDATA"]) / "CollectiveMindGraph").exists(),
}))
"""
    started = time.monotonic()
    completed = subprocess.run(
        [sys.executable, "-c", script],
        env=environment,
        text=True,
        capture_output=True,
        check=True,
        timeout=10,
        cwd=Path(__file__).resolve().parents[1] / "src",
    )
    elapsed = time.monotonic() - started
    payload = json.loads(completed.stdout.strip())

    assert elapsed < 10
    assert payload["title"] == "Collective MindGraph Engine"
    assert payload["factory_title"] == "Collective MindGraph Engine"
    assert payload["storage_exists"] is False


def test_sync_service_builds_without_any_gui_toolkit(tmp_path):
    """The service is a headless deployable and must not need Qt.

    A CI flag alone would not prove this, so the import is exercised with Qt
    made unimportable.
    """

    script = """
import sys

class _Blocked:
    def find_module(self, name, path=None):
        if name == "PySide6" or name.startswith("PySide6."):
            raise ImportError("PySide6 is unavailable in a headless deployment.")
        return None

sys.meta_path.insert(0, _Blocked())

from collective_mindgraph.sync_server.app import create_sync_app
from collective_mindgraph.sync_server.settings import SyncServerSettings

app = create_sync_app(
    SyncServerSettings(database_url="sqlite+aiosqlite:///headless.sqlite3", blob_root=".")
)
assert "PySide6" not in sys.modules
print(app.title)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
    )
    assert completed.stdout.strip() == "Collective MindGraph Sync"
