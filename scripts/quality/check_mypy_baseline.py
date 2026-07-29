"""Run strict mypy and reject any increase in the recorded type-debt baseline."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = ROOT / "quality" / "mypy-baseline.json"
MYPY_COMMAND = (
    sys.executable,
    "-m",
    "mypy",
    "src/collective_mindgraph",
    "--strict",
    "--platform=win32",
    "--show-error-codes",
    "--no-error-summary",
)
ERROR_PATTERN = re.compile(
    r"^(?P<path>src[\\/].+?\.py):\d+(?::\d+)?: error: .+ \[(?P<code>[^\]]+)\]$"
)


def parse_error_budget(lines: Iterable[str]) -> Counter[str]:
    """Group strict-mypy errors by stable module and error code."""

    budget: Counter[str] = Counter()
    for line in lines:
        match = ERROR_PATTERN.match(line.strip())
        if match is None:
            continue
        path = match.group("path").replace("\\", "/")
        budget[f"{path}|{match.group('code')}"] += 1
    return budget


def find_regressions(
    actual: Mapping[str, int],
    baseline: Mapping[str, int],
) -> dict[str, int]:
    """Return only new categories or count increases."""

    return {
        key: count - baseline.get(key, 0)
        for key, count in actual.items()
        if count > baseline.get(key, 0)
    }


def _read_baseline(path: Path) -> dict[str, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(key): int(value) for key, value in payload["errors"].items()}


def _write_baseline(path: Path, errors: Mapping[str, int]) -> None:
    payload = {
        "schema_version": 1,
        "strict": True,
        "scope": "src/collective_mindgraph",
        "total_errors": sum(errors.values()),
        "errors": dict(sorted(errors.items())),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _run_mypy() -> tuple[int, str]:
    completed = subprocess.run(
        MYPY_COMMAND,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    return completed.returncode, output


def _format_changes(changes: Mapping[str, int]) -> str:
    return "\n".join(f"  +{count} {key}" for key, count in sorted(changes.items()))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--update",
        action="store_true",
        help="Record the current debt after confirming that it did not increase.",
    )
    arguments = parser.parse_args(list(argv) if argv is not None else None)

    return_code, output = _run_mypy()
    actual = parse_error_budget(output.splitlines())
    if return_code not in {0, 1}:
        print(output, file=sys.stderr)
        print(f"mypy failed unexpectedly with exit code {return_code}.", file=sys.stderr)
        return return_code
    if return_code == 1 and not actual:
        print(output, file=sys.stderr)
        print("mypy failed, but no typed error records could be parsed.", file=sys.stderr)
        return 2

    baseline = _read_baseline(BASELINE_PATH) if BASELINE_PATH.exists() else {}
    regressions = find_regressions(actual, baseline)
    if baseline and regressions:
        print("Strict mypy debt increased:", file=sys.stderr)
        print(_format_changes(regressions), file=sys.stderr)
        return 1

    if arguments.update:
        _write_baseline(BASELINE_PATH, actual)
        print(f"Recorded {sum(actual.values())} strict mypy errors in {BASELINE_PATH}.")
        return 0
    if not BASELINE_PATH.exists():
        print(
            f"Missing baseline: run {Path(__file__).name} --update after review.",
            file=sys.stderr,
        )
        return 2

    removed = sum(baseline.values()) - sum(actual.values())
    suffix = f"; {removed} baseline errors removed" if removed else ""
    print(f"Strict mypy debt: {sum(actual.values())}/{sum(baseline.values())}{suffix}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
