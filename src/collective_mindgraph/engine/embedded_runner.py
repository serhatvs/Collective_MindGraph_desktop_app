"""Engine runner used by the frozen product executable."""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def run_embedded_engine(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="CollectiveMindGraph.exe --engine")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args(list(argv) if argv is not None else [])
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("The embedded engine can only bind to localhost.")
    import uvicorn

    from collective_mindgraph.engine.main import create_app

    server = uvicorn.Server(
        uvicorn.Config(
            app=create_app(),
            host=args.host,
            port=args.port,
            log_level=args.log_level.lower(),
            log_config=None,
            access_log=False,
            reload=False,
        )
    )
    server.install_signal_handlers = lambda: None
    server.run()
    return 0
