"""Async engine lifecycle and schema creation for the sync service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from .settings import SyncServerSettings
from .tables import METADATA


class SyncDatabase:
    """Owns the async engine without import-time side effects."""

    def __init__(self, settings: SyncServerSettings) -> None:
        self._settings = settings
        self._engine: AsyncEngine | None = None

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            self._engine = create_async_engine(
                self._settings.database_url,
                pool_pre_ping=True,
                future=True,
            )
        return self._engine

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[AsyncConnection]:
        """Run one transaction; foreign keys stay enforced on SQLite too."""

        async with self.engine.begin() as connection:
            if not self._settings.is_postgres:
                await connection.exec_driver_sql("PRAGMA foreign_keys = ON")
            yield connection

    async def create_schema(self) -> None:
        """Create every table for development and test deployments.

        Production deployments use Alembic; this path exists so that a
        self-host smoke test or an ephemeral test database can be prepared
        without a migration run.
        """

        async with self.engine.begin() as connection:
            await connection.run_sync(METADATA.create_all)

    async def dispose(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None


__all__ = ["SyncDatabase"]
