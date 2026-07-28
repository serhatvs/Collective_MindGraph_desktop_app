"""Backup-first migration into the canonical local database."""

from __future__ import annotations

import gc
import hashlib
import os
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .canonical_schema import SCHEMA_VERSION, initialize_schema
from .legacy_backend_import import import_backend_database, import_transcript_archive
from .legacy_desktop_import import import_legacy_desktop
from .migration_support import file_sha256, open_readonly, record_source, table_exists
from .sqlite_database import SqliteDatabase


@dataclass(frozen=True, slots=True)
class MigrationReport:
    migrated: bool
    canonical_path: Path
    backup_path: Path | None = None
    imported_sources: tuple[Path, ...] = ()
    counts: dict[str, int] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


class LegacyDataMigrator:
    """Build and validate a replacement database without mutating its sources."""

    def __init__(
        self,
        canonical_path: Path,
        *,
        backend_database_path: Path | None = None,
        transcript_directory: Path | None = None,
        backend_database_paths: tuple[Path, ...] = (),
        transcript_directories: tuple[Path, ...] = (),
    ) -> None:
        self._canonical_path = canonical_path.expanduser().resolve()
        self._backend_database_paths = self._unique_paths(
            (
                *((backend_database_path,) if backend_database_path is not None else ()),
                *backend_database_paths,
            )
        )
        self._transcript_directories = self._unique_paths(
            (
                *((transcript_directory,) if transcript_directory is not None else ()),
                *transcript_directories,
            )
        )

    def run(self) -> MigrationReport:
        canonical_exists = self._canonical_path.exists()
        canonical_is_current = canonical_exists and self._is_canonical(self._canonical_path)
        canonical_is_legacy = canonical_exists and self._has_legacy_desktop_data(
            self._canonical_path
        )
        if canonical_exists and not canonical_is_current and not canonical_is_legacy:
            raise sqlite3.DatabaseError(
                f"Existing canonical database is not a recognized schema: {self._canonical_path}"
            )
        if (
            canonical_is_current
            and self._schema_version(self._canonical_path) >= SCHEMA_VERSION
            and not self._has_pending_sources()
        ):
            return MigrationReport(
                migrated=False,
                canonical_path=self._canonical_path,
                warnings=(
                    "Canonical database is current and every discovered source "
                    "has already been imported.",
                ),
            )

        backup_path = self._create_backup() if canonical_exists else None
        expected_counts = self._table_counts(backup_path) if canonical_is_current else {}
        target_path = self._canonical_path.with_suffix(self._canonical_path.suffix + ".migrating")
        self._remove_stale_target(target_path)
        if canonical_is_current and backup_path is not None:
            self._backup_sqlite(backup_path, target_path)

        old_schema_version = self._schema_version(backup_path)
        database = SqliteDatabase(target_path)
        initialize_schema(database)
        imported_sources: list[Path] = []
        imported_hashes: list[str] = []
        counts: dict[str, int] = {}

        try:
            with database.connect() as destination:
                if canonical_is_legacy and backup_path is not None:
                    self._import_database_source(
                        backup_path,
                        "legacy_desktop",
                        destination,
                        counts,
                        imported_sources,
                        imported_hashes,
                        import_legacy_desktop,
                    )
                self._import_transcript_directories(
                    destination,
                    counts,
                    imported_sources,
                    imported_hashes,
                )
                self._import_backend_databases(
                    destination,
                    counts,
                    imported_sources,
                    imported_hashes,
                    backup_path,
                )

            self._validate_database(database, imported_hashes, expected_counts)
            self._finalize_target(target_path)
            gc.collect()
            self._activate_target(target_path)
        except BaseException:
            self._discard_target(target_path)
            raise

        migrated = (
            not canonical_exists
            or canonical_is_legacy
            or bool(imported_sources)
            or old_schema_version < self._schema_version(self._canonical_path)
        )
        warnings = (
            ("Canonical database was already current; no legacy source was imported.",)
            if canonical_is_current and not migrated
            else ()
        )
        return MigrationReport(
            migrated=migrated,
            canonical_path=self._canonical_path,
            backup_path=backup_path,
            imported_sources=tuple(imported_sources),
            counts=counts,
            warnings=warnings,
        )

    def _import_transcript_directories(
        self,
        destination: sqlite3.Connection,
        counts: dict[str, int],
        imported_sources: list[Path],
        imported_hashes: list[str],
    ) -> None:
        for directory in self._transcript_directories:
            if not directory.is_dir():
                continue
            source_hash = self._directory_hash(directory)
            if not source_hash or self._already_imported(destination, source_hash):
                continue
            imported = import_transcript_archive(directory, destination)
            self._merge_counts(counts, imported)
            record_source(
                destination,
                source_hash=source_hash,
                source_path=directory,
                source_kind="legacy_transcript_archive",
                details=imported,
            )
            imported_sources.append(directory)
            imported_hashes.append(source_hash)

    def _import_backend_databases(
        self,
        destination: sqlite3.Connection,
        counts: dict[str, int],
        imported_sources: list[Path],
        imported_hashes: list[str],
        backup_path: Path | None,
    ) -> None:
        for path in self._backend_database_paths:
            if not path.is_file() or path == self._canonical_path or path == backup_path:
                continue
            self._import_database_source(
                path,
                "legacy_engine",
                destination,
                counts,
                imported_sources,
                imported_hashes,
                import_backend_database,
            )

    def _import_database_source(
        self,
        path: Path,
        source_kind: str,
        destination: sqlite3.Connection,
        counts: dict[str, int],
        imported_sources: list[Path],
        imported_hashes: list[str],
        importer,
    ) -> None:
        source_hash = file_sha256(path)
        if self._already_imported(destination, source_hash):
            return
        source = open_readonly(path)
        try:
            imported = importer(source, destination)
        finally:
            source.close()
        self._merge_counts(counts, imported)
        record_source(
            destination,
            source_hash=source_hash,
            source_path=path,
            source_kind=source_kind,
            details=imported,
        )
        imported_sources.append(path)
        imported_hashes.append(source_hash)

    @staticmethod
    def _already_imported(destination: sqlite3.Connection, source_hash: str) -> bool:
        return (
            destination.execute(
                "SELECT 1 FROM migration_sources WHERE source_hash = ?",
                (source_hash,),
            ).fetchone()
            is not None
        )

    @staticmethod
    def _merge_counts(target: dict[str, int], source: dict[str, int]) -> None:
        for key, value in source.items():
            target[key] = target.get(key, 0) + value

    @staticmethod
    def _is_canonical(path: Path) -> bool:
        try:
            connection = open_readonly(path)
            try:
                return table_exists(connection, "schema_migrations") and table_exists(
                    connection, "meetings"
                )
            finally:
                connection.close()
        except sqlite3.DatabaseError:
            return False

    @staticmethod
    def _has_legacy_desktop_data(path: Path) -> bool:
        try:
            connection = open_readonly(path)
            try:
                return table_exists(connection, "sessions")
            finally:
                connection.close()
        except sqlite3.DatabaseError:
            return False

    def _create_backup(self) -> Path:
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        backup_path = self._canonical_path.with_name(
            f"{self._canonical_path.stem}.pre-rework-{timestamp}.bak"
        )
        self._backup_sqlite(self._canonical_path, backup_path)
        return backup_path

    def _has_pending_sources(self) -> bool:
        connection = open_readonly(self._canonical_path)
        try:
            imported_hashes = {
                str(row[0])
                for row in connection.execute(
                    "SELECT source_hash FROM migration_sources"
                ).fetchall()
            }
        finally:
            connection.close()
        for directory in self._transcript_directories:
            if not directory.is_dir():
                continue
            source_hash = self._directory_hash(directory)
            if source_hash and source_hash not in imported_hashes:
                return True
        for path in self._backend_database_paths:
            if not path.is_file() or path == self._canonical_path:
                continue
            if file_sha256(path) not in imported_hashes:
                return True
        return False

    @staticmethod
    def _backup_sqlite(source_path: Path, backup_path: Path) -> None:
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        source = sqlite3.connect(str(source_path))
        backup = sqlite3.connect(str(backup_path))
        try:
            source.backup(backup)
        finally:
            backup.close()
            source.close()

    def _remove_stale_target(self, target_path: Path) -> None:
        if target_path.parent != self._canonical_path.parent:
            raise RuntimeError("Migration target escaped the canonical database directory.")
        self._discard_target(target_path)

    @staticmethod
    def _discard_target(target_path: Path) -> None:
        for path in (
            target_path,
            Path(f"{target_path}-wal"),
            Path(f"{target_path}-shm"),
        ):
            if path.exists():
                path.unlink()

    def _activate_target(self, target_path: Path) -> None:
        if not self._canonical_path.exists():
            self._replace_with_retry(target_path, self._canonical_path)
            return
        retired_path = self._canonical_path.with_suffix(
            self._canonical_path.suffix + ".legacy-source"
        )
        if retired_path.exists():
            retired_path.unlink()
        self._replace_with_retry(self._canonical_path, retired_path)
        try:
            self._replace_with_retry(target_path, self._canonical_path)
        except BaseException:
            self._replace_with_retry(retired_path, self._canonical_path)
            raise
        retired_path.unlink()

    @staticmethod
    def _replace_with_retry(source: Path, target: Path) -> None:
        for attempt in range(20):
            try:
                os.replace(source, target)
                return
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.05)

    @staticmethod
    def _directory_hash(directory: Path) -> str:
        files = sorted(directory.glob("*.json"))
        if not files:
            return ""
        digest = hashlib.sha256()
        for path in files:
            digest.update(path.name.encode("utf-8"))
            digest.update(file_sha256(path).encode("ascii"))
        return digest.hexdigest()

    @staticmethod
    def _validate_database(
        database: SqliteDatabase,
        imported_hashes: list[str],
        expected_counts: dict[str, int],
    ) -> None:
        with database.connect() as connection:
            integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
            foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
            actual_tables = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            recorded_hashes = {
                str(row[0])
                for row in connection.execute(
                    "SELECT source_hash FROM migration_sources"
                ).fetchall()
            }
            actual_counts = {
                table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in expected_counts
            }
        if integrity.lower() != "ok":
            raise RuntimeError(f"Migrated database failed integrity check: {integrity}")
        if foreign_keys:
            raise RuntimeError(
                f"Migrated database contains {len(foreign_keys)} foreign-key violations."
            )
        required_tables = {
            "meetings",
            "recordings",
            "transcripts",
            "transcript_segments",
            "insights",
            "evidence_references",
            "knowledge_nodes",
            "knowledge_edges",
            "embeddings",
            "processing_jobs",
            "schema_migrations",
            "migration_sources",
        }
        missing_tables = required_tables - actual_tables
        if missing_tables:
            raise RuntimeError(
                f"Migrated database is missing required tables: {sorted(missing_tables)}"
            )
        if set(imported_hashes) - recorded_hashes:
            raise RuntimeError("Migrated database did not record every imported source hash.")
        decreased = {
            table: (expected, actual_counts[table])
            for table, expected in expected_counts.items()
            if actual_counts[table] < expected
        }
        if decreased:
            raise RuntimeError(f"Migrated database lost canonical rows: {decreased}")

    @staticmethod
    def _unique_paths(paths: tuple[Path, ...]) -> tuple[Path, ...]:
        result: list[Path] = []
        seen: set[Path] = set()
        for path in paths:
            resolved = path.expanduser().resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            result.append(resolved)
        return tuple(result)

    @staticmethod
    def _schema_version(path: Path | None) -> int:
        if path is None or not path.exists():
            return 0
        connection = open_readonly(path)
        try:
            if not table_exists(connection, "schema_migrations"):
                return 0
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
            ).fetchone()
            return int(row[0]) if row else 0
        finally:
            connection.close()

    @staticmethod
    def _finalize_target(path: Path) -> None:
        connection = sqlite3.connect(str(path), isolation_level=None)
        try:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            connection.execute("PRAGMA journal_mode = DELETE")
        finally:
            connection.close()

    @staticmethod
    def _table_counts(path: Path | None) -> dict[str, int]:
        if path is None or not path.exists():
            return {}
        connection = open_readonly(path)
        try:
            tables = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
                if not str(row[0]).startswith("sqlite_")
            }
            return {
                table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in tables
            }
        finally:
            connection.close()
