from __future__ import annotations

import ast
import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "collective_mindgraph"


def _python_files(directory: Path):
    return tuple(path for path in directory.rglob("*.py") if "__pycache__" not in path.parts)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                source_relative = path.relative_to(ROOT / "src").with_suffix("")
                package_parts = list(source_relative.parts[:-1])
                keep = len(package_parts) - (node.level - 1)
                resolved_parts = package_parts[:keep]
                if node.module:
                    resolved_parts.extend(node.module.split("."))
                names.add(".".join(resolved_parts))
            elif node.module:
                names.add(node.module)
    return names


def test_dependency_direction_is_enforced():
    forbidden = {
        "domain": (
            "collective_mindgraph.application",
            "collective_mindgraph.infrastructure",
            "collective_mindgraph.engine",
            "collective_mindgraph.desktop",
        ),
        "application": (
            "collective_mindgraph.infrastructure",
            "collective_mindgraph.engine",
            "collective_mindgraph.desktop",
        ),
        "infrastructure": ("collective_mindgraph.engine", "collective_mindgraph.desktop"),
        "engine": ("collective_mindgraph.desktop",),
        "desktop": ("collective_mindgraph.engine",),
    }
    violations: list[str] = []
    for layer, prefixes in forbidden.items():
        for path in _python_files(PACKAGE / layer):
            for imported in _imports(path):
                if imported.startswith(prefixes):
                    violations.append(f"{path.relative_to(ROOT)} -> {imported}")
    assert violations == []


def test_ambiguous_and_legacy_production_modules_are_absent():
    forbidden_names = {"models.py", "services.py", "utils.py"}
    found = [
        str(path.relative_to(ROOT))
        for path in _python_files(PACKAGE)
        if path.name in forbidden_names
    ]
    legacy_roots = [
        PACKAGE / "core",
        PACKAGE / "services",
        PACKAGE / "engine" / "services",
        PACKAGE / "infrastructure" / "database",
    ]
    found.extend(
        str(path.relative_to(ROOT)) for root in legacy_roots for path in _python_files(root)
    )
    assert found == []


def test_production_module_size_limit_and_documented_allowlist():
    configuration = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    policy = configuration["tool"]["collective-mindgraph"]["architecture"]
    limit = int(policy["line_limit"])
    allowlist = set(policy["line_limit_allowlist"])
    oversized = {
        path.relative_to(PACKAGE).as_posix()
        for path in _python_files(PACKAGE)
        if len(path.read_text(encoding="utf-8").splitlines()) > limit
    }
    assert oversized == allowlist


def test_no_runtime_path_injection():
    violations = []
    for root in (PACKAGE, ROOT / "scripts"):
        for path in _python_files(root):
            source = path.read_text(encoding="utf-8")
            if "sys.path." in source or "PYTHONPATH" in source:
                violations.append(str(path.relative_to(ROOT)))
    assert violations == []


def test_language_catalog_keys_match():
    catalog_dir = PACKAGE / "desktop" / "i18n"
    english = json.loads((catalog_dir / "en.json").read_text(encoding="utf-8"))
    turkish = json.loads((catalog_dir / "tr.json").read_text(encoding="utf-8"))
    assert english.keys() == turkish.keys()
    assert all(value.strip() for value in english.values())
    assert all(value.strip() for value in turkish.values())
