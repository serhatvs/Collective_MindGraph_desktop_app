"""Canonical V2 domain registry based on ``Book.xlsx``."""

from __future__ import annotations

from collective_mindgraph.collaboration_tool.manifest import MANIFEST as COLLABORATION_TOOL
from collective_mindgraph.enterprise_software.manifest import MANIFEST as ENTERPRISE_SOFTWARE
from collective_mindgraph.knowledge_management_tool.manifest import (
    MANIFEST as KNOWLEDGE_MANAGEMENT_TOOL,
)
from collective_mindgraph.meeting_assistant.manifest import MANIFEST as MEETING_ASSISTANT
from collective_mindgraph.productivity_tool.manifest import MANIFEST as PRODUCTIVITY_TOOL
from collective_mindgraph.smart_assistant.manifest import MANIFEST as SMART_ASSISTANT

DOMAIN_CONTRACTS = (
    MEETING_ASSISTANT,
    KNOWLEDGE_MANAGEMENT_TOOL,
    PRODUCTIVITY_TOOL,
    ENTERPRISE_SOFTWARE,
    COLLABORATION_TOOL,
    SMART_ASSISTANT,
)

SPREADSHEET_SECTIONS = tuple(contract.spreadsheet_name for contract in DOMAIN_CONTRACTS)
