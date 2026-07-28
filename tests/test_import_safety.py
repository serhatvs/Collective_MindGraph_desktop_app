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
