"""Contracts describing module responsibilities and allowed dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SubmoduleKind = Literal[
    "service",
    "provider",
    "repository",
    "model_group",
    "policy",
    "internal_package",
]


@dataclass(frozen=True, slots=True)
class SubmoduleContract:
    """A spreadsheet subsection mapped to a bounded software component."""

    spreadsheet_name: str
    package: str
    responsibility: str
    kind: SubmoduleKind
    public_interfaces: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DomainContract:
    """A top-level spreadsheet section mapped to a major domain package."""

    spreadsheet_name: str
    package: str
    responsibility: str
    public_interfaces: tuple[str, ...]
    submodules: tuple[SubmoduleContract, ...]
    allowed_dependencies: tuple[str, ...] = ()
    forbidden_dependencies: tuple[str, ...] = ("ui",)


@dataclass(frozen=True, slots=True)
class DependencyRule:
    """A human-readable import/dependency rule for boundary checks."""

    source: str
    may_depend_on: tuple[str, ...] = field(default_factory=tuple)
    must_not_depend_on: tuple[str, ...] = field(default_factory=tuple)
    rationale: str = ""
