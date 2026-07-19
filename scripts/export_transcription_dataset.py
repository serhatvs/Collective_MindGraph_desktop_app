"""Export reviewed transcription segments as CSV, JSONL, and HF AudioFolder data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.transcript_annotation.dataset import AnnotationDataset  # noqa: E402
from tools.transcript_annotation.exporter import EXPORT_FORMATS, export_reviewed_dataset  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--formats", nargs="+", choices=EXPORT_FORMATS, default=list(EXPORT_FORMATS))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset = AnnotationDataset.load(args.dataset)
    output = args.output or (dataset.root / "exports" / "reviewed")
    summary = export_reviewed_dataset(dataset, output, formats=args.formats)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not summary["warnings"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
