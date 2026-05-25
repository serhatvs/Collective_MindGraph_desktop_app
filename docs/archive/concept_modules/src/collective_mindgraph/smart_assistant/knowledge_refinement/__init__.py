"""Knowledge refinement service submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.shared import KnowledgeRecordId


class KnowledgeRefiner(Protocol):
    """Improves stored memory structure over time from feedback and usage."""

    def refine_records(self, record_ids: tuple[KnowledgeRecordId, ...]) -> tuple[KnowledgeRecordId, ...]:
        """Return records that were refined or regenerated."""
