"""Top-level launcher for desktop and embedded-backend modes."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import sys

from .app import run as run_desktop
from .runtime_paths import app_storage_dir, is_frozen_build


def run(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "--backend":
        _write_launcher_log(f"dispatch=backend args={arguments!r}")
        from .embedded_backend import run_embedded_backend

        return run_embedded_backend(arguments[1:])
    _write_launcher_log(f"dispatch=desktop args={arguments!r}")
    return run_desktop()


def _write_launcher_log(message: str) -> None:
    if not is_frozen_build():
        return
    path = app_storage_dir() / "launcher.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{message}\n")
