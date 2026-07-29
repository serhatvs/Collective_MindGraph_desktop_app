"""Operator commands for schema preparation, retention, and inspection."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence

from .blob_storage import FilesystemBlobStore
from .database import SyncDatabase
from .principals import BootstrapTokenResolver
from .service import SyncService
from .settings import SyncServerSettings, get_sync_server_settings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mindgraph-admin")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("create-schema", help="Create every table for a fresh deployment.")
    commands.add_parser("purge", help="Apply every retention window once.")
    commands.add_parser("show-retention", help="Print the configured retention windows.")
    arguments = parser.parse_args(list(argv) if argv is not None else None)

    settings = get_sync_server_settings()
    if arguments.command == "show-retention":
        print(json.dumps(retention_summary(settings), indent=2, sort_keys=True))
        return 0
    if arguments.command == "create-schema":
        asyncio.run(_create_schema(settings))
        return 0
    report = asyncio.run(_purge(settings))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def retention_summary(settings: SyncServerSettings) -> dict[str, int]:
    """Return the retention windows this deployment enforces."""

    return {
        "content_days": settings.content_retention_days,
        "audit_days": settings.audit_retention_days,
        "backup_days": settings.backup_retention_days,
    }


async def _create_schema(settings: SyncServerSettings) -> None:
    database = SyncDatabase(settings)
    try:
        await database.create_schema()
    finally:
        await database.dispose()


async def _purge(settings: SyncServerSettings) -> dict[str, int]:
    database = SyncDatabase(settings)
    service = SyncService(
        settings=settings,
        database=database,
        identities=BootstrapTokenResolver({"unused": "operator"}),
        blob_store=FilesystemBlobStore(settings.blob_root),
    )
    try:
        return await service.purge_expired()
    finally:
        await database.dispose()


__all__ = ["main", "retention_summary"]
