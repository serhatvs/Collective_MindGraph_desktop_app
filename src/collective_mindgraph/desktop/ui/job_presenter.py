"""Thread-pool presenter for non-blocking engine calls."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _TaskSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(object)


class _Task(QRunnable):
    def __init__(self, operation: Callable[[], Any]) -> None:
        super().__init__()
        self.operation = operation
        self.signals = _TaskSignals()

    def run(self) -> None:
        try:
            result = self.operation()
        except Exception as exc:  # propagated to the UI thread
            self.signals.failed.emit(exc)
        else:
            self.signals.succeeded.emit(result)


class JobPresenter(QObject):
    busy_changed = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        self._active: set[_Task] = set()

    def submit(
        self,
        operation: Callable[[], Any],
        *,
        succeeded: Callable[[Any], None],
        failed: Callable[[Exception], None],
    ) -> None:
        task = _Task(operation)
        self._active.add(task)
        self.busy_changed.emit(True)

        def finish() -> None:
            self._active.discard(task)
            self.busy_changed.emit(bool(self._active))

        def on_success(result: object) -> None:
            finish()
            succeeded(result)

        def on_failure(error: object) -> None:
            finish()
            failed(error if isinstance(error, Exception) else RuntimeError(str(error)))

        task.signals.succeeded.connect(on_success)
        task.signals.failed.connect(on_failure)
        self._pool.start(task)
