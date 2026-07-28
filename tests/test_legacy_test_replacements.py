from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "legacy_test_replacements.json"


def test_every_removed_legacy_test_module_has_an_explained_replacement():
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entries = payload["replacements"]
    patterns = [entry["legacy_id_pattern"] for entry in entries]

    assert payload["baseline_characterized_test_count"] == 407
    assert len(patterns) == len(set(patterns)) == 44
    assert all(
        pattern.startswith("tests/test_") and pattern.endswith(".py::*") for pattern in patterns
    )
    assert all(entry["reason"].strip() for entry in entries)
    assert all(entry["replaced_by"] for entry in entries)
    for entry in entries:
        for replacement in entry["replaced_by"]:
            assert (ROOT / replacement).is_file(), replacement
