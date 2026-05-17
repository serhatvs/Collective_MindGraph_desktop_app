"""Access-control policy submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.shared import KnowledgeRecordId, OrganizationId, UserId


class AccessPolicy(Protocol):
    """Answers authorization questions for memory and assistant workflows."""

    def can_read_record(
        self,
        user_id: UserId,
        organization_id: OrganizationId,
        record_id: KnowledgeRecordId,
    ) -> bool:
        """Return whether a user can read a knowledge record."""
