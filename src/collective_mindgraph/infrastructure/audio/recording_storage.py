"""Contained managed storage for retryable recording audio."""

from __future__ import annotations

from pathlib import Path

from collective_mindgraph.domain import MeetingId, RecordingId


class ManagedRecordingStorage:
    URI_PREFIX = "managed://"

    def __init__(self, root: Path) -> None:
        self._root = root.expanduser().resolve()

    @property
    def root(self) -> Path:
        return self._root

    def allocate(
        self,
        meeting_id: MeetingId,
        recording_id: RecordingId,
        original_name: str,
    ) -> tuple[Path, str]:
        suffix = Path(original_name).suffix.lower()
        if not suffix or len(suffix) > 12 or not suffix[1:].isalnum():
            suffix = ".bin"
        relative = Path(str(int(meeting_id))) / f"{recording_id}{suffix}"
        path = self._contained(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path, f"{self.URI_PREFIX}{relative.as_posix()}"

    def resolve(self, source_uri: str) -> Path:
        if not source_uri.startswith(self.URI_PREFIX):
            raise ValueError("Recording is not owned by managed storage.")
        relative = Path(source_uri.removeprefix(self.URI_PREFIX))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Managed recording path is invalid.")
        return self._contained(relative)

    def delete(self, source_uri: str) -> bool:
        path = self.resolve(source_uri)
        if not path.exists():
            return False
        path.unlink()
        return True

    def _contained(self, relative: Path) -> Path:
        candidate = (self._root / relative).resolve()
        try:
            candidate.relative_to(self._root)
        except ValueError as exc:
            raise ValueError("Managed recording escaped its storage directory.") from exc
        return candidate
