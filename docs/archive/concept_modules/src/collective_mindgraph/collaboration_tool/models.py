"""Collaboration and workspace model group."""

from __future__ import annotations

from dataclasses import dataclass

from collective_mindgraph.shared import OrganizationId, UserId, WorkspaceId


@dataclass(frozen=True, slots=True)
class WorkspaceMember:
    user_id: UserId
    role: str


@dataclass(frozen=True, slots=True)
class Workspace:
    workspace_id: WorkspaceId
    organization_id: OrganizationId
    name: str
    members: tuple[WorkspaceMember, ...] = ()
