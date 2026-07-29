"""Chunk storage for encrypted blobs.

The service stores sealed chunks and verifies their declared digests. It never
decrypts a chunk, so integrity is the only property it can and does enforce.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Protocol


class BlobStore(Protocol):
    """Object storage for sealed blob chunks."""

    def put(self, storage_key: str, payload: bytes) -> None: ...

    def get(self, storage_key: str) -> bytes: ...

    def delete_prefix(self, prefix: str) -> int: ...


class FilesystemBlobStore:
    """Local-disk adapter used by self-host deployments and tests.

    S3-compatible deployments substitute an adapter with the same contract; the
    storage key layout is intentionally identical so a migration is a copy.
    """

    def __init__(self, root: Path) -> None:
        self._root = Path(root).expanduser()

    def put(self, storage_key: str, payload: bytes) -> None:
        destination = self._path(storage_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)

    def get(self, storage_key: str) -> bytes:
        return self._path(storage_key).read_bytes()

    def delete_prefix(self, prefix: str) -> int:
        directory = self._path(prefix)
        if not directory.is_dir():
            return 0
        removed = 0
        for path in sorted(directory.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
                removed += 1
            elif path.is_dir():
                path.rmdir()
        directory.rmdir()
        return removed

    def _path(self, storage_key: str) -> Path:
        if not storage_key.strip():
            raise ValueError("A storage key is required.")
        candidate = (self._root / storage_key).resolve()
        root = self._root.resolve()
        if not candidate.is_relative_to(root):
            raise ValueError("Storage keys may not escape the blob root.")
        return candidate


def chunk_storage_key(workspace_id: str, manifest_id: str, chunk_index: int) -> str:
    """Return the deterministic key one sealed chunk is stored under."""

    return f"{workspace_id}/{manifest_id}/{chunk_index:08d}.chunk"


def manifest_prefix(workspace_id: str, manifest_id: str) -> str:
    """Return the prefix holding every chunk of one manifest."""

    return f"{workspace_id}/{manifest_id}"


def digest(payload: bytes) -> str:
    """Return the lowercase hexadecimal SHA-256 of sealed bytes."""

    return hashlib.sha256(payload).hexdigest()


__all__ = [
    "BlobStore",
    "FilesystemBlobStore",
    "chunk_storage_key",
    "digest",
    "manifest_prefix",
]
