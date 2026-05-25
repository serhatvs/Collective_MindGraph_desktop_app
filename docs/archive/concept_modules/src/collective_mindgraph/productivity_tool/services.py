"""Public service boundary for productivity automation."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.shared import OrganizationId
from .models import AutomationRun


class ProductivityService(Protocol):
    """Coordinates governed automation over org memory outputs."""

    def run_scheduled_automation(self, organization_id: OrganizationId) -> AutomationRun:
        """Refresh task, decision, and summary views for an organization."""
