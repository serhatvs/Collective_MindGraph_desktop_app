"""Product-level dispatch for desktop and frozen engine modes."""

from __future__ import annotations

import sys
from collections.abc import Sequence


def run(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "--engine":
        from collective_mindgraph.engine.embedded_runner import run_embedded_engine

        return run_embedded_engine(arguments[1:])
    from collective_mindgraph.desktop.launcher import run_desktop

    return run_desktop(arguments)
