"""Productivity automation model group."""

from __future__ import annotations

from dataclasses import dataclass

from collective_mindgraph.shared import OrganizationId, UserId


@dataclass(frozen=True, slots=True)
class AutomationRun:
    organization_id: OrganizationId
    trigger: str
    produced_record_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FilterDecision:
    user_id: UserId | None
    reason: str
    redacted_text: str
    was_modified: bool
