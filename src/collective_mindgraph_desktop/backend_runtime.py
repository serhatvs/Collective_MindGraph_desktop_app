"""Local backend lifecycle helpers for the desktop app."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys
from urllib.parse import urlparse

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

from .runtime_paths import (
    embedded_backend_data_dir,
    embedded_backend_temp_dir,
    executable_dir,
    is_frozen_build,
)


@dataclass(frozen=True, slots=True)
class BackendLaunchSpec:
    program: str
    arguments: list[str]
    working_directory: str
    environment: dict[str, str] = field(default_factory=dict)


def build_local_backend_launch_spec(base_url: str, repo_root: Path | None = None) -> BackendLaunchSpec | None:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"}:
        return None
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        return None

    host = parsed.hostname or "127.0.0.1"
    port = str(parsed.port or 8080)

    if is_frozen_build():
        return BackendLaunchSpec(
            program=str(Path(sys.executable).resolve()),
            arguments=["--backend", "--host", host, "--port", port],
            working_directory=str(executable_dir()),
            environment={
                "CMG_RT_DATA_DIR": str(embedded_backend_data_dir()),
                "CMG_RT_TEMP_DIR": str(embedded_backend_temp_dir()),
                "CMG_RT_VAD_PROVIDER": "energy",
                "CMG_RT_DIARIZER_PROVIDER": "fallback",
            },
        )

    root = (repo_root or Path.cwd()).resolve()
    backend_dir = root / "realtime_backend"
    app_entry = backend_dir / "app" / "main.py"
    if not app_entry.exists():
        return None

    python_candidates = [
        backend_dir / ".venv" / "Scripts" / "python.exe",
        backend_dir / ".venv" / "bin" / "python",
        Path(sys.executable),
    ]
    program = None
    for candidate in python_candidates:
        if candidate.exists():
            program = str(candidate)
            break
    if program is None:
        return None

    return BackendLaunchSpec(
        program=program,
        arguments=["-m", "uvicorn", "app.main:app", "--host", host, "--port", port],
        working_directory=str(backend_dir),
    )


class LocalBackendManager(QObject):
    state_changed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, repo_root: Path | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._repo_root = (repo_root or Path.cwd()).resolve()
        self._process: QProcess | None = None
        self._last_spec: BackendLaunchSpec | None = None
        self._started_by_app = False

    @property
    def started_by_app(self) -> bool:
        return self._started_by_app

    def can_manage(self, base_url: str) -> bool:
        return build_local_backend_launch_spec(base_url, self._repo_root) is not None

    def ensure_running(self, base_url: str) -> bool:
        if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
            return False

        spec = build_local_backend_launch_spec(base_url, self._repo_root)
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
        process.errorOccurred.connect(self._handle_process_error)
        process.finished.connect(self._handle_process_finished)
        process.start()
        if not process.waitForStarted(3_000):
            error_message = process.errorString() or "Failed to start the local transcription backend."
            process.deleteLater()
            self.error_occurred.emit(error_message)
            return False

        self._process = process
        self._last_spec = spec
        self._started_by_app = True
        self.state_changed.emit(
            f"Started local backend with {Path(spec.program).name} on {base_url}."
        )
        return True

    def shutdown(self) -> None:
        if self._process is None:
            return
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.terminate()
            if not self._process.waitForFinished(2_000):
                self._process.kill()
                self._process.waitForFinished(2_000)
        self._cleanup_process()

    def _handle_process_error(self, _error) -> None:
        if self._process is None:
            return
        self.error_occurred.emit(self._process.errorString() or "Local backend process failed.")

    def _handle_process_finished(self, _exit_code: int, _exit_status) -> None:
        if self._started_by_app and self._last_spec is not None:
            self.state_changed.emit("Local backend process stopped.")
        self._cleanup_process()

    def _cleanup_process(self) -> None:
        if self._process is not None:
            self._process.deleteLater()
        self._process = None
        self._last_spec = None
        self._started_by_app = False
