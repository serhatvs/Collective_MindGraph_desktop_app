"""Command-line entry point for the synchronization service."""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mindgraph-sync-server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--log-level", default="info")
    parser.add_argument(
        "--create-schema",
        action="store_true",
        help="Create tables on startup instead of running Alembic first.",
    )
    arguments = parser.parse_args(list(argv) if argv is not None else None)

    import uvicorn

    from .app import create_sync_app

    uvicorn.run(
        create_sync_app(create_schema=arguments.create_schema),
        host=arguments.host,
        port=arguments.port,
        log_level=arguments.log_level.lower(),
    )
    return 0


__all__ = ["main"]
