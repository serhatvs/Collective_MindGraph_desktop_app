"""QSettings-backed desktop-only device and experimental preferences."""

from __future__ import annotations

from PySide6.QtCore import QSettings


class DesktopPreferenceStore:
    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings or QSettings("CollectiveMindGraph", "Desktop")

    @property
    def audio_device_id(self) -> str | None:
        value = str(self._settings.value("audio/input_device_id", "") or "").strip()
        return value or None

    @audio_device_id.setter
    def audio_device_id(self, value: str | None) -> None:
        self._settings.setValue("audio/input_device_id", value or "")

    @property
    def wake_phrase_enabled(self) -> bool:
        return self._bool("labs/wake_phrase_enabled")

    @wake_phrase_enabled.setter
    def wake_phrase_enabled(self, value: bool) -> None:
        self._settings.setValue("labs/wake_phrase_enabled", value)

    @property
    def expert_asr_enabled(self) -> bool:
        return self._bool("labs/expert_asr_enabled")

    @expert_asr_enabled.setter
    def expert_asr_enabled(self, value: bool) -> None:
        self._settings.setValue("labs/expert_asr_enabled", value)

    def _bool(self, key: str) -> bool:
        value = self._settings.value(key, False)
        if isinstance(value, bool):
            return value
        return str(value).casefold() in {"1", "true", "yes", "on"}
