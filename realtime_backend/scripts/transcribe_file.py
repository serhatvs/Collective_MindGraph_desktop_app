"""Upload a local media file to the realtime backend file endpoint."""

from __future__ import annotations

import argparse
from pathlib import Path

import httpx


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Upload a file to the realtime backend.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--url", default="http://127.0.0.1:8080/transcribe/file")
    parser.add_argument("--language", default=None)
    parser.add_argument("--timeout", type=float, default=600.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.source.exists():
        raise SystemExit(f"File not found: {args.source}")

    with httpx.Client(timeout=args.timeout) as client:
        with args.source.open("rb") as handle:
            response = client.post(
                args.url,
                files={"upload": (args.source.name, handle, "application/octet-stream")},
                data={"language": args.language or ""},
            )
        response.raise_for_status()

    payload = response.json()
    print(payload.get("text_output", ""))
    if payload.get("transcript", {}).get("summary"):
        print("\nSummary:\n")
        print(payload["transcript"]["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
