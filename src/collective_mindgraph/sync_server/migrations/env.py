"""Alembic environment for the synchronization service schema."""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from collective_mindgraph.sync_server.tables import METADATA

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = METADATA


def _database_url() -> str:
    configured = os.environ.get("CMG_SYNC_DATABASE_URL", "").strip()
    if configured:
        return configured
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("CMG_SYNC_DATABASE_URL must be set before running migrations.")
    return url


def run_migrations_offline() -> None:
    """Emit SQL for review without connecting to the database."""

    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    engine = create_async_engine(_database_url())
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_run)
            await connection.commit()
    finally:
        await engine.dispose()


def run_migrations_online() -> None:
    """Apply migrations against the configured database."""

    asyncio.run(_run_async())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
