"""Metadata tagging service submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.knowledge_management_tool.models import KnowledgeRecord, KnowledgeTag


class MetadataTagger(Protocol):
    """Categorizes memory records for filtering, search, and governance."""

    def suggest_tags(self, record: KnowledgeRecord) -> tuple[KnowledgeTag, ...]:
        """Return candidate tags for one knowledge record."""
