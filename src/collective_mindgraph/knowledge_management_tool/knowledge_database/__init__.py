"""Knowledge database repository submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.shared import KnowledgeRecordId, OrganizationId
from collective_mindgraph.knowledge_management_tool.models import KnowledgeRecord


class KnowledgeRepository(Protocol):
    """Persistence boundary for structured organizational memory."""

    def save(self, record: KnowledgeRecord) -> KnowledgeRecordId:
        """Persist or replace a record."""

    def get(self, record_id: KnowledgeRecordId) -> KnowledgeRecord | None:
        """Load a record by ID."""

    def list_for_org(self, organization_id: OrganizationId) -> tuple[KnowledgeRecord, ...]:
        """List records available inside an organization."""
