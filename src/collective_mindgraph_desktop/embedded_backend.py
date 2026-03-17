"""Embedded realtime backend runner for frozen desktop builds."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import traceback

from .runtime_paths import app_storage_dir


def run_embedded_backend(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="CollectiveMindGraph.exe --backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args(list(argv) if argv is not None else [])

    _write_debug_log("embedded backend entry")
    try:
        import uvicorn

        from realtime_backend.app.main import build_app

        _write_debug_log("imports loaded")
        config = uvicorn.Config(
            app=build_app(),
            host=args.host,
            port=args.port,
            log_level=args.log_level.lower(),
            reload=False,
        )
        _write_debug_log(f"uvicorn configured for {args.host}:{args.port}")
        server = uvicorn.Server(config)
        server.install_signal_handlers = lambda: None
        server.run()
        _write_debug_log("uvicorn server exited normally")
        return 0
    except Exception:  # pragma: no cover - defensive logging for frozen builds
        _write_debug_log(traceback.format_exc())
        return 1


def _crash_log_path() -> Path:
    path = app_storage_dir() / "embedded_backend.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _write_debug_log(message: str) -> None:
    path = _crash_log_path()
    if not path.exists():
        path.write_text("", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{message}\n")
