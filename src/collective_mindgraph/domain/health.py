"""Typed runtime health reported to product interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProviderHealth(StrEnum):
    READY = "ready"
    DEGRADED = "degraded"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class EngineHealth:
    status: ProviderHealth
    engine_version: str
    transcription: ProviderHealth
    embeddings: ProviderHealth
    local_llm: ProviderHealth
    detail: str = ""
