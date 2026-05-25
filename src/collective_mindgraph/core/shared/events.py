"""Small event primitive for crossing module boundaries asynchronously later."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, Mapping
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """A durable fact emitted by a domain without importing downstream modules."""

    name: str
    payload: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
