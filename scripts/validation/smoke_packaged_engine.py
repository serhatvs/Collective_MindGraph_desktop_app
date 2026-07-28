"""Start a packaged engine, verify its typed health endpoint, and stop it."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.request
from collections.abc import Sequence
from pathlib import Path


def _free_loopback_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    arguments = parser.parse_args(list(argv) if argv is not None else None)
    executable = arguments.executable.expanduser().resolve()
    if not executable.is_file():
        parser.error(f"packaged executable does not exist: {executable}")

    port = _free_loopback_port()
    with tempfile.TemporaryDirectory(prefix="cmg-packaged-smoke-") as directory:
        root = Path(directory)
        environment = {
            **os.environ,
            "CMG_RT_DATA_DIR": str(root / "data"),
            "CMG_RT_TEMP_DIR": str(root / "temp"),
            "CMG_DATABASE_PATH": str(root / "collective_mindgraph.sqlite3"),
            "CMG_RT_ASR_PROVIDER": "mock",
            "CMG_RT_VAD_PROVIDER": "energy",
            "CMG_RT_DIARIZER_PROVIDER": "fallback",
            "CMG_EMBEDDING_PROVIDER": "disabled",
            "CMG_LOCAL_LLM_PROVIDER": "disabled",
        }
        process = subprocess.Popen(
            [
                str(executable),
                "--engine",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "warning",
            ],
            cwd=executable.parent,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            payload = _wait_for_health(process, port)
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        finally:
            _stop(process)
    return 0


def _wait_for_health(process: subprocess.Popen[str], port: int) -> dict[str, object]:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/v1/health",
                timeout=1,
            ) as response:
                return dict(json.load(response))
        except OSError:
            if process.poll() is not None:
                stderr = process.stderr.read() if process.stderr else ""
                raise RuntimeError(f"Packaged engine exited during startup: {stderr}")
            time.sleep(0.2)
    raise TimeoutError("Packaged engine health endpoint did not become ready.")


def _stop(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        process.wait(timeout=5)
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
