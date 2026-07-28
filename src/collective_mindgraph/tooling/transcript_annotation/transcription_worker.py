"""Qt worker for running local annotation transcription off the UI thread."""

from __future__ import annotations

import asyncio
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget

from .pipeline import transcribe_for_annotation


class TranscriptionWorker(QThread):
    completed = Signal(str, object)
    failed = Signal(str, str)

    def __init__(
        self,
        audio_path: Path,
        profile: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.audio_path = audio_path
        self.profile = profile

    def run(self) -> None:
        try:
            transcript = asyncio.run(
                transcribe_for_annotation(self.audio_path, profile=self.profile)
            )
            self.completed.emit(str(self.audio_path), transcript)
        except Exception as exc:
            self.failed.emit(str(self.audio_path), f"{type(exc).__name__}: {exc}")
