"""Reusable loading, empty, offline, retry, and error presentation."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout

from ..language_catalog import LanguageCatalog


class StatePanel(QFrame):
    retry_requested = Signal()

    def __init__(self, catalog: LanguageCatalog, parent=None) -> None:
        super().__init__(parent)
        self._catalog = catalog
        layout = QVBoxLayout(self)
        self._message = QLabel()
        self._message.setObjectName("Muted")
        self._message.setWordWrap(True)
        self._retry = QPushButton()
        self._retry.clicked.connect(self.retry_requested)
        layout.addWidget(self._message)
        layout.addWidget(self._retry)
        layout.addStretch()
        self.hide()
        catalog.language_changed.connect(self._retranslate)
        self._state = "empty"
        self._detail = ""

    def show_state(self, state: str, detail: str = "") -> None:
        self._state = state
        self._detail = detail
        self._retranslate()
        self.show()

    def clear(self) -> None:
        self.hide()

    def _retranslate(self) -> None:
        key = {
            "loading": "common.loading",
            "empty": "common.empty",
            "offline": "common.offline",
            "error": "common.error",
        }.get(self._state, "common.error")
        message = self._catalog.text(key)
        self._message.setText(f"{message}\n{self._detail}".strip())
        self._retry.setText(self._catalog.text("common.retry"))
        self._retry.setVisible(self._state in {"offline", "error"})
