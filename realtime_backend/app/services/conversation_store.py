"""Filesystem-backed transcript persistence."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from ..models import ConversationTranscript


class ConversationStore:
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def save(self, transcript: ConversationTranscript) -> Path:
        path = self.path_for(transcript.conversation_id)
        with self._lock:
            path.write_text(transcript.model_dump_json(indent=2), encoding="utf-8")
        return path

    def get(self, conversation_id: str) -> ConversationTranscript | None:
        path = self.path_for(conversation_id)
        if not path.exists():
            return None
        with self._lock:
            payload = json.loads(path.read_text(encoding="utf-8"))
        return ConversationTranscript.model_validate(payload)

    def path_for(self, conversation_id: str) -> Path:
        return self._base_dir / f"{conversation_id}.json"
