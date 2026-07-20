#!/usr/bin/env python3
"""Install friend-alpha desktop and real-ASR dependencies."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import textwrap
from pathlib import Path


def _run_step(label: str, command: list[str], *, cwd: Path) -> bool:
    print(f"\n[CMG] {label}")
    print(f"[CMG] Running: {' '.join(command)}")
    result = subprocess.run(command, cwd=str(cwd))
    if result.returncode != 0:
        print(f"\n[CMG] ERROR: {label} failed with exit code {result.returncode}.", file=sys.stderr)
        return False
    return True


def _faster_whisper_available() -> tuple[bool, str | None]:
    try:
        spec = importlib.util.find_spec("faster_whisper")
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"
    return spec is not None, None


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    requirements_path = repo_root / "realtime_backend" / "requirements.txt"
    pyproject_path = repo_root / "pyproject.toml"

    print(textwrap.dedent(f"""\
        ================================================
        Collective MindGraph -- Friend Alpha Setup
        ================================================
        Python executable : {sys.executable}
        Repo root         : {repo_root}
    """))

    if not pyproject_path.exists():
        print(f"[CMG] ERROR: Missing project file: {pyproject_path}", file=sys.stderr)
        return 1
    if not requirements_path.exists():
        print(f"[CMG] ERROR: Missing backend requirements file: {requirements_path}", file=sys.stderr)
        return 1

    steps = [
        (
            "Install desktop app and validation dependencies",
            [sys.executable, "-m", "pip", "install", "-e", ".[dev]"],
        ),
        (
            "Install backend and real transcription dependencies",
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_path)],
        ),
    ]

    for label, command in steps:
        if not _run_step(label, command, cwd=repo_root):
            return 1

    faster_whisper_ok, faster_whisper_error = _faster_whisper_available()
    print("\n[CMG] Verifying real ASR dependency...")
    print(f"[CMG] faster_whisper available: {faster_whisper_ok}")
    if faster_whisper_error:
        print(f"[CMG] faster_whisper check detail: {faster_whisper_error}", file=sys.stderr)

    if not faster_whisper_ok:
        print(
            "\n[CMG] ERROR: Real transcription is not ready. The launcher may use mock fallback.\n"
            "      Check the pip output above and try again in a Python 3.11+ environment.",
            file=sys.stderr,
        )
        return 1

    print("\n[CMG] Friend alpha dependencies are ready.")
    print("[CMG] Next: python scripts\\launch\\launch_cmg.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
