"""Command-line entry point for the localhost engine."""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mindgraph-engine")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--log-level", default="info")
    arguments = parser.parse_args(list(argv) if argv is not None else None)
    if arguments.host not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("the engine may only bind to localhost")

    import uvicorn

    from .main import create_app

    uvicorn.run(
        create_app(),
        host=arguments.host,
        port=arguments.port,
        log_level=arguments.log_level.lower(),
    )
    return 0
