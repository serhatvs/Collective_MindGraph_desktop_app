"""Command-line entry point for the transcript annotation application."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    from .app import AnnotationWindow

    args = parse_args(argv)
    application = QApplication.instance() or QApplication(sys.argv)
    window = AnnotationWindow(args.dataset)
    window.show()
    return application.exec()
