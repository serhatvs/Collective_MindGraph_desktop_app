"""Lifecycle management for the localhost engine process."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

from .runtime_paths import (
    app_storage_dir,
    embedded_engine_temp_dir,
    executable_dir,
    is_frozen_build,
)


@dataclass(frozen=True, slots=True)
class EngineLaunchSpec:
    program: str
    arguments: list[str]
    working_directory: str
    environment: dict[str, str] = field(default_factory=dict)


def build_local_engine_launch_spec(base_url: str) -> EngineLaunchSpec | None:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        return None
    host = parsed.hostname or "127.0.0.1"
    port = str(parsed.port or 8080)
    if is_frozen_build():
        return EngineLaunchSpec(
            program=str(Path(sys.executable).resolve()),
            arguments=["--engine", "--host", host, "--port", port],
            working_directory=str(executable_dir()),
            environment={
                "CMG_RT_DATA_DIR": str(app_storage_dir()),
                "CMG_RT_TEMP_DIR": str(embedded_engine_temp_dir()),
                "CMG_RT_VAD_PROVIDER": "energy",
            },
        )
    return EngineLaunchSpec(
        program=str(Path(sys.executable).resolve()),
        arguments=[
            "-m",
            "collective_mindgraph.engine",
            "--host",
            host,
            "--port",
            port,
        ],
        working_directory=str(Path.cwd().resolve()),
    )


class LocalEngineManager(QObject):
    state_changed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._started_by_app = False
        self._recent_output = ""

    @property
    def started_by_app(self) -> bool:
        return self._started_by_app

    @property
    def recent_output(self) -> str:
        """Return the bounded tail of engine output for diagnostics."""

        return self._recent_output

    def can_manage(self, base_url: str) -> bool:
        return build_local_engine_launch_spec(base_url) is not None

    def ensure_running(self, base_url: str) -> bool:
        if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
            return False
        spec = build_local_engine_launch_spec(base_url)
        if spec is None:
            return False
        process = QProcess(self)
        process.setWorkingDirectory(spec.working_directory)
        process.setProgram(spec.program)
        process.setArguments(spec.arguments)
        if spec.environment:
            environment = QProcessEnvironment.systemEnvironment()
            for key, value in spec.environment.items():
                environment.insert(key, value)
            process.setProcessEnvironment(environment)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(lambda: self._collect_output(process))
        process.errorOccurred.connect(
            lambda _error: self.error_occurred.emit(
                process.errorString() or "Local engine process failed."
            )
        )
        process.finished.connect(lambda *_args: self._finished())
        process.start()
        if not process.waitForStarted(3_000):
            self.error_occurred.emit(process.errorString() or "Failed to start the local engine.")
            process.deleteLater()
            return False
        self._process = process
        self._started_by_app = True
        self.state_changed.emit(f"Local engine started on {base_url}.")
        return True

    def shutdown(self) -> None:
        if self._process is None:
            return
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.terminate()
            if not self._process.waitForFinished(3_000):
                self._process.kill()
                self._process.waitForFinished(2_000)
        self._finished()

    def _finished(self) -> None:
        if self._process is not None:
            self._collect_output(self._process)
            self._process.deleteLater()
        self._process = None
        self._started_by_app = False
        self.state_changed.emit("Local engine stopped.")

    def _collect_output(self, process: QProcess) -> None:
        raw_output = process.readAllStandardOutput().data()
        output = bytes(raw_output).decode("utf-8", errors="replace")
        if output:
            self._recent_output = (self._recent_output + output)[-16_384:]
