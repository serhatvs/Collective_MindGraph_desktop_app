"""Shared background workers for UI tasks."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from ..transcription import (
    RealtimeBackendTranscriptionConfig,
    RealtimeBackendTranscriptionService,
    BackendHealthStatus,
)

from .jobs import JOB_REGISTRY, JobStatus

class BackendTranscriptionWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress_updated = Signal(int, str)

    def __init__(
        self,
        audio_path: str,
        config: RealtimeBackendTranscriptionConfig,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._audio_path = audio_path
        self._config = config
        self._job = JOB_REGISTRY.create_job("transcription", f"Processing {audio_path}")

    @Slot()
    def run(self) -> None:
        JOB_REGISTRY.update_job(self._job.id, status=JobStatus.RUNNING, progress=10)
        self.progress_updated.emit(10, "Starting transcription...")
        try:
            result = RealtimeBackendTranscriptionService(config=self._config).transcribe_file(self._audio_path)
            JOB_REGISTRY.update_job(self._job.id, status=JobStatus.SUCCEEDED, progress=100, message="Complete")
            self.progress_updated.emit(100, "Extraction complete")
        except Exception as exc:
            JOB_REGISTRY.update_job(self._job.id, status=JobStatus.FAILED, error=str(exc), message="Failed")
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)


class BackendHealthWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        config: RealtimeBackendTranscriptionConfig,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config

    @Slot()
    def run(self) -> None:
        try:
            result = RealtimeBackendTranscriptionService(config=self._config).fetch_health()
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)
