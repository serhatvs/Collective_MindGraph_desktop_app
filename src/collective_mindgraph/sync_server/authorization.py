"""One place where every workspace operation proves its authorization."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncConnection

from .contracts import Principal, Role
from .database import SyncDatabase
from .membership_repository import MembershipRepository


class AuthorizedOperations:
    """Opens a transaction only after the caller's role has been checked."""

    def __init__(self, database: SyncDatabase, members: MembershipRepository) -> None:
        self.database = database
        self.members = members

    @asynccontextmanager
    async def authorized(
        self,
        *,
        workspace_id: str,
        principal: Principal,
        minimum: Role,
    ) -> AsyncIterator[AsyncConnection]:
        """Yield a transaction in which the caller is known to hold ``minimum``."""

        async with self.database.begin() as connection:
            await self.members.require_role(
                connection,
                workspace_id=workspace_id,
                principal=principal,
                minimum=minimum,
            )
            yield connection


__all__ = ["AuthorizedOperations"]
