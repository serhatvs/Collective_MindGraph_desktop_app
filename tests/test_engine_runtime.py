import json
import os
import socket
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QProcess

from collective_mindgraph.desktop.engine_runtime import (
    LocalEngineManager,
    build_local_engine_launch_spec,
)


def test_source_engine_launch_spec_uses_canonical_module():
    spec = build_local_engine_launch_spec("http://127.0.0.1:9090")

    assert spec is not None
    assert Path(spec.program) == Path(sys.executable).absolute()
    assert spec.arguments == [
        "-m",
        "collective_mindgraph.engine",
        "--host",
        "127.0.0.1",
        "--port",
        "9090",
    ]


def test_engine_launch_spec_rejects_non_loopback_urls():
    assert build_local_engine_launch_spec("https://example.com:8080") is None


def test_frozen_engine_launch_spec_uses_embedded_mode(tmp_path, monkeypatch):
    executable_path = tmp_path / "CollectiveMindGraph.exe"
    executable_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable_path))

    spec = build_local_engine_launch_spec("http://127.0.0.1:8080")

    assert spec is not None
    assert Path(spec.program) == executable_path
    assert spec.arguments == ["--engine", "--host", "127.0.0.1", "--port", "8080"]
    assert spec.working_directory == str(executable_path.parent)
    assert spec.environment["CMG_RT_DATA_DIR"].replace("\\", "/").endswith("CollectiveMindGraph")
    assert (
        spec.environment["CMG_RT_TEMP_DIR"].replace("\\", "/").endswith("CollectiveMindGraph/temp")
    )


def test_engine_manager_stops_owned_process(qapp):
    events: list[str] = []

    class FakeProcess:
        def state(self):
            return QProcess.ProcessState.Running

        def terminate(self):
            events.append("terminate")

        def waitForFinished(self, timeout):  # noqa: N802 - Qt test double
            events.append(f"wait:{timeout}")
            return True

        def readAllStandardOutput(self):  # noqa: N802 - Qt test double
            return QByteArray()

        def deleteLater(self):  # noqa: N802 - Qt test double
            events.append("delete")

    manager = LocalEngineManager()
    manager._process = FakeProcess()  # type: ignore[assignment]

    manager.shutdown()

    assert qapp is not None
    assert events == ["terminate", "wait:3000", "delete"]
    assert manager.started_by_app is False


def test_engine_manager_bounds_recent_diagnostic_output(qapp):
    class FakeOutputProcess:
        def readAllStandardOutput(self):  # noqa: N802 - Qt test double
            return QByteArray(b"x" * 20_000)

    manager = LocalEngineManager()
    manager._collect_output(FakeOutputProcess())  # type: ignore[arg-type]

    assert qapp is not None
    assert manager.recent_output == "x" * 16_384


def test_engine_manager_autostarts_and_stops_real_source_engine(tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = int(listener.getsockname()[1])
    url = f"http://127.0.0.1:{port}"
    database_path = (tmp_path / "collective_mindgraph.sqlite3").resolve()
    environment = {
        **os.environ,
        "CMG_RT_DATA_DIR": str(tmp_path / "data"),
        "CMG_RT_TEMP_DIR": str(tmp_path / "temp"),
        "CMG_DATABASE_PATH": str(database_path),
        "CMG_RT_ASR_PROVIDER": "mock",
        "CMG_RT_VAD_PROVIDER": "energy",
        "CMG_RT_DIARIZER_PROVIDER": "fallback",
        "CMG_EMBEDDING_PROVIDER": "disabled",
        "CMG_LOCAL_LLM_PROVIDER": "disabled",
    }
    script = f"""
import json
import time
import urllib.request
from PySide6.QtCore import QCoreApplication
from collective_mindgraph.desktop.engine_runtime import LocalEngineManager

application = QCoreApplication([])
manager = LocalEngineManager()
url = {url!r}
try:
    assert manager.ensure_running(url)
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        application.processEvents()
        try:
            with urllib.request.urlopen(url + "/api/v1/health", timeout=1) as response:
                payload = json.load(response)
            break
        except OSError:
            time.sleep(0.1)
    else:
        raise AssertionError(
            "Desktop-owned source engine did not become healthy. "
            f"Engine output: {{manager.recent_output}}"
        )
    assert manager.started_by_app
finally:
    manager.shutdown()
print(json.dumps({{"payload": payload, "started": manager.started_by_app}}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout.strip())

    assert result["payload"]["database_path"] == str(database_path)
    assert result["started"] is False
