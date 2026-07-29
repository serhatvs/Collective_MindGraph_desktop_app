"""Workspace and synchronization identity persistence ports."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.domain import SyncIdentity, Workspace, WorkspaceId


class WorkspaceStore(Protocol):
    def local_workspace(self) -> Workspace: ...

    def get(self, workspace_id: WorkspaceId) -> Workspace | None: ...

    def list(self) -> tuple[Workspace, ...]: ...


class SyncIdentityStore(Protocol):
    def get_identity(self, table: str, local_id: int | str) -> SyncIdentity | None: ...
