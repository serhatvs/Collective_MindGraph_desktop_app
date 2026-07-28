"""Deterministic discovery of user-owned legacy persistence sources."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LegacySourceCandidates:
    """Ordered, de-duplicated legacy sources considered during migration."""

    backend_databases: tuple[Path, ...]
    transcript_directories: tuple[Path, ...]


def discover_legacy_sources(
    *,
    canonical_path: Path,
    data_directory: Path,
    working_directory: Path | None = None,
    executable_path: Path | None = None,
) -> LegacySourceCandidates:
    """Return legacy sources in precedence order without touching the filesystem."""

    cwd = (working_directory or Path.cwd()).expanduser().resolve()
    executable = executable_path or (
        Path(sys.executable) if getattr(sys, "frozen", False) else None
    )
    executable_directory = (
        executable.expanduser().resolve().parent if executable is not None else None
    )
    canonical_directory = canonical_path.expanduser().resolve().parent
    configured_backend = _configured_path("CMG_LEGACY_BACKEND_DATABASE")
    configured_archive = _configured_path("CMG_LEGACY_TRANSCRIPT_DIRECTORY")

    legacy_roots = [cwd / "realtime_backend_data"]
    if executable_directory is not None:
        legacy_roots.append(executable_directory / "realtime_backend_data")

    backend_candidates: list[Path | None] = [configured_backend]
    backend_candidates.extend(root / "collective_mindgraph.sqlite3" for root in legacy_roots)
    backend_candidates.append(data_directory / "legacy_backend.sqlite3")

    archive_candidates: list[Path | None] = [configured_archive]
    archive_candidates.extend(root / "transcripts" for root in legacy_roots)
    archive_candidates.append(canonical_directory / "transcripts")

    return LegacySourceCandidates(
        backend_databases=_unique_resolved(backend_candidates),
        transcript_directories=_unique_resolved(archive_candidates),
    )


def _configured_path(environment_name: str) -> Path | None:
    value = os.environ.get(environment_name, "").strip()
    return Path(value) if value else None


def _unique_resolved(candidates: list[Path | None]) -> tuple[Path, ...]:
    result: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate is None:
            continue
        resolved = candidate.expanduser().resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        result.append(resolved)
    return tuple(result)
