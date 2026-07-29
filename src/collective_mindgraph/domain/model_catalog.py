"""Signed model catalogue entries and install state.

Nothing here downloads anything. The catalogue describes what *could* be
installed; installing is always a separate, explicit act by the user.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
VERSION_PATTERN = re.compile(r"^\d+(\.\d+){0,3}([-.][0-9A-Za-z.-]+)?$")


class ModelStatus(StrEnum):
    """Where one catalogue entry stands on this machine."""

    AVAILABLE = "available"
    DOWNLOADING = "downloading"
    INSTALLED = "installed"
    FAILED = "failed"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class ModelEntry:
    """One signed catalogue entry."""

    model_id: str
    version: str
    provider: str
    size_bytes: int
    license: str
    url: str
    sha256: str
    min_engine: str

    def __post_init__(self) -> None:
        for name, value in (
            ("model id", self.model_id),
            ("provider", self.provider),
            ("license", self.license),
        ):
            if not value.strip():
                raise ValueError(f"A catalogue entry needs a {name}.")
        if not VERSION_PATTERN.match(self.version):
            raise ValueError(f"Unusable model version: {self.version!r}.")
        if not VERSION_PATTERN.match(self.min_engine):
            raise ValueError(f"Unusable minimum engine version: {self.min_engine!r}.")
        if self.size_bytes <= 0:
            raise ValueError("A catalogue entry needs a positive size.")
        # Normalise rather than merely accept: the installer compares against a
        # computed lowercase digest, so an uppercase entry would otherwise fail
        # verification for a file that was perfectly correct.
        object.__setattr__(self, "sha256", self.sha256.strip().lower())
        if not SHA256_PATTERN.match(self.sha256):
            raise ValueError("A catalogue entry needs a SHA-256 digest.")
        # Model bytes are fetched over the public internet, so the transport has
        # to be authenticated even though the digest is checked afterwards.
        if not self.url.startswith("https://"):
            raise ValueError("Model downloads must use HTTPS.")

    @property
    def key(self) -> tuple[str, str]:
        return (self.model_id, self.version)

    def supports_engine(self, engine_version: str) -> bool:
        """Whether this entry may run on an engine of the given version."""

        return _version_tuple(engine_version) >= _version_tuple(self.min_engine)


@dataclass(frozen=True, slots=True)
class InstalledModel:
    """One entry as it exists on disk."""

    model_id: str
    version: str
    path: str
    sha256: str
    size_bytes: int
    installed_at: datetime
    pinned: bool = False

    def __post_init__(self) -> None:
        if not self.path.strip():
            raise ValueError("An installed model needs a path.")
        if self.installed_at.tzinfo is None:
            raise ValueError("The install timestamp must be timezone-aware.")
        object.__setattr__(self, "sha256", self.sha256.strip().lower())
        if not SHA256_PATTERN.match(self.sha256):
            raise ValueError("An installed model needs a SHA-256 digest.")


class ModelConsentError(RuntimeError):
    """Raised when an install would proceed without the user's agreement."""


class ModelVerificationError(RuntimeError):
    """Raised when a catalogue or a downloaded file fails verification."""


def _version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in value.split("-")[0].split("."):
        if not chunk.isdigit():
            break
        parts.append(int(chunk))
    return tuple(parts) or (0,)


__all__ = [
    "SHA256_PATTERN",
    "InstalledModel",
    "ModelConsentError",
    "ModelEntry",
    "ModelStatus",
    "ModelVerificationError",
]
