"""Shared cursor pagination contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class PageRequest:
    cursor: str | None = None
    limit: int = 50

    def __post_init__(self) -> None:
        if not 1 <= self.limit <= 200:
            raise ValueError("Page limit must be between 1 and 200.")


@dataclass(frozen=True, slots=True)
class Page(Generic[T]):
    items: tuple[T, ...]
    total: int
    next_cursor: str | None = None
