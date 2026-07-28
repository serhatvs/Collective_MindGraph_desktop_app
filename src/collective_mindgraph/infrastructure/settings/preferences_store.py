"""Small atomic JSON store for user-adjustable engine preferences."""

from __future__ import annotations

import json
from pathlib import Path


class EnginePreferenceStore:
    _ALLOWED_KEYS = frozenset(
        {
            "default_language",
            "transcription_quality_mode",
            "asr_provider",
            "asr_model_name",
            "embedding_provider",
            "llm_provider",
            "diarization_enabled",
            "retain_raw_audio",
        }
    )

    def __init__(self, path: Path) -> None:
        self._path = path.resolve()

    def load(self) -> dict[str, object]:
        if not self._path.exists():
            return {}
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        return {key: value for key, value in payload.items() if key in self._ALLOWED_KEYS}

    def save(self, changes: dict[str, object]) -> dict[str, object]:
        unknown = set(changes) - self._ALLOWED_KEYS
        if unknown:
            raise ValueError(f"Unsupported engine preferences: {sorted(unknown)}")
        merged = {**self.load(), **changes}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(f"{self._path.suffix}.tmp")
        temporary.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(self._path)
        return merged
