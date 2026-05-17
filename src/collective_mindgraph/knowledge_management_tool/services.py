"""Public service boundary for organizational memory workflows."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.shared import KnowledgeRecordId, OrganizationId

from .models import KnowledgeLink, KnowledgeRecord


class KnowledgeManagementService(Protocol):
    """Coordinates storage, metadata, and contextual linking."""

    def store_record(self, record: KnowledgeRecord) -> KnowledgeRecordId:
        """Persist one structured knowledge record."""

    def link_related_context(self, organization_id: OrganizationId) -> tuple[KnowledgeLink, ...]:
        """Refresh context links within an organization's memory graph."""
