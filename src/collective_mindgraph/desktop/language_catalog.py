"""Runtime-switchable UTF-8 desktop language catalog."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QLocale, QObject, QSettings, Signal


class LanguageCatalog(QObject):
    language_changed = Signal(str)

    def __init__(self, settings: QSettings | None = None) -> None:
        super().__init__()
        self._settings = settings or QSettings("CollectiveMindGraph", "Desktop")
        stored = str(self._settings.value("ui/language", "") or "")
        system_language = QLocale.system().name().split("_", maxsplit=1)[0].casefold()
        self._language = (
            stored if stored in {"en", "tr"} else ("tr" if system_language == "tr" else "en")
        )
        self._catalogs = {language: _load_catalog(language) for language in ("en", "tr")}
        if self._catalogs["en"].keys() != self._catalogs["tr"].keys():
            raise RuntimeError("English and Turkish catalog keys must match.")

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, language: str) -> None:
        normalized = language.casefold()
        if normalized not in self._catalogs:
            normalized = "en"
        if normalized == self._language:
            return
        self._language = normalized
        self._settings.setValue("ui/language", normalized)
        self.language_changed.emit(normalized)

    def text(self, key: str, **values: object) -> str:
        template = self._catalogs[self._language].get(
            key,
            self._catalogs["en"].get(key, key),
        )
        return template.format(**values) if values else template


def _load_catalog(language: str) -> dict[str, str]:
    path = Path(__file__).with_name("i18n") / f"{language}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Language catalog {language} must contain an object.")
    return {str(key): str(value) for key, value in payload.items()}
