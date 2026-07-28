"""Desktop-only launcher with no engine-layer dependency."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from collective_mindgraph import __version__


def run_desktop(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mindgraph",
        description="Open the Collective MindGraph desktop workspace.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.parse_args(list(argv) if argv is not None else [])
    from .app import run

    return run()


def run(argv: Sequence[str] | None = None) -> int:
    return run_desktop(argv)
