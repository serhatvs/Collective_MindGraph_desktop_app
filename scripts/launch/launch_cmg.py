#!/usr/bin/env python3
"""
launch_cmg.py - Collective MindGraph desktop launcher.

Usage:
    python scripts/launch/launch_cmg.py

Sets PYTHONPATH to include src/ and the repo root, checks whether the real
local ASR dependency is importable, then launches the desktop app via:
    python -m collective_mindgraph_desktop

Exit codes:
    0  - app exited normally
    1  - launch error (import failure, bad environment, etc.)
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import textwrap
from pathlib import Path


def _check_faster_whisper_available() -> tuple[bool, str | None]:
    try:
        spec = importlib.util.find_spec("faster_whisper")
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"
    return spec is not None, None


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    src_dir = repo_root / "src"

    if not src_dir.is_dir():
        print(
            f"[CMG] ERROR: Expected 'src/' directory at:\n"
            f"      {src_dir}\n\n"
            "      Make sure the repository checkout is complete.",
            file=sys.stderr,
        )
        return 1

    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    additions = [str(src_dir), str(repo_root)]
    new_path_parts = additions + [p for p in existing.split(os.pathsep) if p]
    env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(new_path_parts))

    faster_whisper_available, faster_whisper_error = _check_faster_whisper_available()
    faster_whisper_status = "available" if faster_whisper_available else "missing"

    print(textwrap.dedent(f"""\
        ================================================
        Collective MindGraph -- Alpha Launcher
        ================================================
        Python executable : {sys.executable}
        Repo root         : {repo_root}
        PYTHONPATH        : {env['PYTHONPATH']}
        faster_whisper    : {faster_whisper_status}
    """))

    if not faster_whisper_available:
        print(
            "[CMG] WARNING: Real transcription is not available. "
            "The app may use mock fallback.\n"
            "      Install backend ASR dependencies before friend testing:\n"
            "      python -m pip install -r realtime_backend\\requirements.txt",
            file=sys.stderr,
        )
        if faster_whisper_error:
            print(f"      Import check detail: {faster_whisper_error}", file=sys.stderr)

    cmd = [sys.executable, "-m", "collective_mindgraph_desktop"]
    print(f"[CMG] Launching: {' '.join(cmd)}\n")

    try:
        result = subprocess.run(cmd, env=env, cwd=str(repo_root))
    except FileNotFoundError:
        print(
            "[CMG] ERROR: Python executable not found.\n"
            f"      Tried: {sys.executable}\n\n"
            "      Make sure Python 3.11+ is installed and on your PATH.",
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        print("\n[CMG] Stopped by user (Ctrl+C).")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[CMG] ERROR: Unexpected launch failure:\n      {exc}", file=sys.stderr)
        return 1

    if result.returncode != 0:
        print(
            f"\n[CMG] App exited with code {result.returncode}.\n"
            "      If the app crashed, check the terminal output above for\n"
            "      tracebacks and report them using the GitHub bug report template:\n"
            "      .github/ISSUE_TEMPLATE/alpha_bug_report.md",
            file=sys.stderr,
        )

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
