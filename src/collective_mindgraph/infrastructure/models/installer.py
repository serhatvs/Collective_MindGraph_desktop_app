"""Consent-gated, resumable, digest-verified model installation.

Nothing downloads without an explicit decision recorded against the exact
model version and its licence. A partial file is resumed rather than restarted,
and a file whose digest does not match the catalogue is deleted rather than
kept, so a corrupted or substituted download cannot become an installed model.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from collective_mindgraph.domain.model_catalog import (
    InstalledModel,
    ModelConsentError,
    ModelEntry,
    ModelVerificationError,
)

CHUNK_BYTES = 1024 * 1024
PARTIAL_SUFFIX = ".partial"

# A source that yields bytes starting at a given offset, so a resumed download
# does not refetch what is already on disk.
ByteSource = Callable[[str, int], Iterator[bytes]]


@dataclass(frozen=True, slots=True)
class ModelConsent:
    """One user's agreement to install one exact model version."""

    model_id: str
    version: str
    license: str
    accepted_at: datetime

    def __post_init__(self) -> None:
        if self.accepted_at.tzinfo is None:
            raise ValueError("The consent timestamp must be timezone-aware.")

    def covers(self, entry: ModelEntry) -> bool:
        """Consent is per version and per licence, never blanket.

        A new version may carry different licence terms, so agreeing once does
        not agree to whatever arrives next.
        """

        return (
            self.model_id == entry.model_id
            and self.version == entry.version
            and self.license == entry.license
        )


@dataclass(frozen=True, slots=True)
class DownloadProgress:
    """How far a download has got."""

    model_id: str
    version: str
    received_bytes: int
    total_bytes: int

    @property
    def fraction(self) -> float:
        return min(1.0, self.received_bytes / self.total_bytes) if self.total_bytes else 0.0


class ModelInstaller:
    """Installs catalogue entries into a version-independent directory."""

    def __init__(
        self,
        root: Path,
        *,
        source: ByteSource,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._root = Path(root).expanduser()
        self._source = source
        self._clock = clock or (lambda: datetime.now(tz=UTC))

    def target_path(self, entry: ModelEntry) -> Path:
        """Where one version lives, outside any application version."""

        return self._root / entry.model_id / entry.version / "model.bin"

    def partial_path(self, entry: ModelEntry) -> Path:
        return self.target_path(entry).with_name("model.bin" + PARTIAL_SUFFIX)

    def install(
        self,
        entry: ModelEntry,
        *,
        consent: ModelConsent | None,
        engine_version: str,
        on_progress: Callable[[DownloadProgress], None] | None = None,
    ) -> InstalledModel:
        """Download and verify one model version."""

        if consent is None or not consent.covers(entry):
            raise ModelConsentError(
                "Installing a model requires accepting that exact version and licence."
            )
        if not entry.supports_engine(engine_version):
            raise ModelVerificationError(
                f"{entry.model_id} {entry.version} requires engine {entry.min_engine} or newer."
            )

        target = self.target_path(entry)
        partial = self.partial_path(entry)
        target.parent.mkdir(parents=True, exist_ok=True)
        received = partial.stat().st_size if partial.exists() else 0
        if received > entry.size_bytes:
            # A partial file larger than the declared size cannot be a prefix
            # of the real one, so resuming from it would be wrong.
            partial.unlink()
            received = 0

        with partial.open("ab") as stream:
            for chunk in self._source(entry.url, received):
                stream.write(chunk)
                received += len(chunk)
                if on_progress is not None:
                    on_progress(
                        DownloadProgress(
                            model_id=entry.model_id,
                            version=entry.version,
                            received_bytes=received,
                            total_bytes=entry.size_bytes,
                        )
                    )

        digest = _digest(partial)
        if received != entry.size_bytes or digest != entry.sha256:
            partial.unlink(missing_ok=True)
            raise ModelVerificationError(
                f"{entry.model_id} {entry.version} failed verification and was discarded."
            )
        os.replace(partial, target)
        return InstalledModel(
            model_id=entry.model_id,
            version=entry.version,
            path=str(target),
            sha256=digest,
            size_bytes=received,
            installed_at=self._clock(),
        )

    def remove(self, model_id: str, version: str, *, pinned: bool = False) -> bool:
        """Remove one installed version unless the user pinned it."""

        if pinned:
            raise ModelVerificationError("A pinned model version cannot be removed.")
        directory = self._root / model_id / version
        if not directory.exists():
            return False
        shutil.rmtree(directory)
        return True

    def installed_versions(self, model_id: str) -> tuple[str, ...]:
        """List versions present on disk, newest name last."""

        directory = self._root / model_id
        if not directory.is_dir():
            return ()
        return tuple(
            sorted(
                child.name
                for child in directory.iterdir()
                if child.is_dir() and (child / "model.bin").exists()
            )
        )


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_BYTES):
            hasher.update(chunk)
    return hasher.hexdigest()


__all__ = [
    "CHUNK_BYTES",
    "PARTIAL_SUFFIX",
    "ByteSource",
    "DownloadProgress",
    "ModelConsent",
    "ModelInstaller",
]
