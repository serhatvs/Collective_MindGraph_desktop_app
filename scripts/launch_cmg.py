#!/usr/bin/env python3
"""
launch_cmg.py — Collective MindGraph desktop launcher.

Usage (from repo root):
    python scripts/launch_cmg.py

Sets PYTHONPATH to include src/ and the repo root, then launches the desktop
app via `python -m collective_mindgraph_desktop`.

Exit codes:
    0  — app exited normally
    1  — launch error (import failure, bad environment, etc.)
"""

import os
import sys
import subprocess
import textwrap
from pathlib import Path


def main() -> int:
    # ── Resolve repo root ────────────────────────────────────────────────────
    # This script lives at <repo>/scripts/launch_cmg.py
    repo_root = Path(__file__).resolve().parent.parent
    src_dir = repo_root / "src"

    if not src_dir.is_dir():
        print(
            f"[CMG] ERROR: Expected 'src/' directory at:\n"
            f"      {src_dir}\n\n"
            "      Make sure you are running this script from the repo root,\n"
            "      or that the repository is not corrupted.",
            file=sys.stderr,
        )
        return 1

    # ── Build PYTHONPATH ─────────────────────────────────────────────────────
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    additions = [str(src_dir), str(repo_root)]
    new_path_parts = additions + [p for p in existing.split(os.pathsep) if p]
    env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(new_path_parts))  # dedup, order-stable

    # ── Announce ─────────────────────────────────────────────────────────────
    print(textwrap.dedent(f"""\
        ================================================
        Collective MindGraph -- Alpha Launcher
        ================================================
        Repo root : {repo_root}
        PYTHONPATH: {env['PYTHONPATH']}
        Python    : {sys.executable}
    """))

    # ── Launch ───────────────────────────────────────────────────────────────
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
