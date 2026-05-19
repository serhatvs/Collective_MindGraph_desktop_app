"""Status badge component for visual feedback."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget


class StatusBadge(QLabel):
    def __init__(self, text: str, stage: str = "idle", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("VoiceStatusBadge")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_stage(stage)

    def set_stage(self, stage: str) -> None:
        self.setProperty("stage", stage)
        self.style().unpolish(self)
        self.style().polish(self)
