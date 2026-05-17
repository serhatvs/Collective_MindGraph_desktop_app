"""Sensitive-data filtering service submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.shared import UserId
from collective_mindgraph.productivity_tool.models import FilterDecision


class DataFilter(Protocol):
    """Redacts or removes sensitive data before indexing or response generation."""

    def filter_text(self, text: str, user_id: UserId | None = None) -> FilterDecision:
        """Return safe text and an audit-friendly filtering decision."""
