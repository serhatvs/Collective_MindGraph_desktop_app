from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _free_loopback_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def test_source_engine_starts_serves_health_and_stops(tmp_path: Path):
    port = _free_loopback_port()
    environment = {
        **os.environ,
        "CMG_RT_DATA_DIR": str(tmp_path / "data"),
        "CMG_RT_TEMP_DIR": str(tmp_path / "temp"),
        "CMG_DATABASE_PATH": str(tmp_path / "collective_mindgraph.sqlite3"),
        "CMG_RT_ASR_PROVIDER": "mock",
        "CMG_RT_VAD_PROVIDER": "energy",
        "CMG_RT_DIARIZER_PROVIDER": "fallback",
        "CMG_EMBEDDING_PROVIDER": "disabled",
        "CMG_LOCAL_LLM_PROVIDER": "disabled",
    }
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "collective_mindgraph.engine",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/v1/health",
                    timeout=1,
                ) as response:
                    payload = json.load(response)
                break
            except OSError:
                if process.poll() is not None:
                    stderr = process.stderr.read() if process.stderr else ""
                    raise AssertionError(f"Engine exited during startup: {stderr}")
                time.sleep(0.1)
        else:
            raise AssertionError("Engine health endpoint did not become ready.")

        assert payload["status"] == "degraded"
        assert payload["database_path"].endswith("collective_mindgraph.sqlite3")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
