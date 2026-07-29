"""Cursor invalidation fan-out.

Notifications carry a workspace identifier and a cursor only. They never carry
ciphertext, so a client always reacts by pulling through the authorized path.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

MAX_QUEUED_NOTIFICATIONS = 32


@dataclass(frozen=True, slots=True)
class CursorNotification:
    """A hint that a workspace advanced past a cursor."""

    workspace_id: str
    cursor: str


class CursorBroadcaster:
    """In-process fan-out of cursor hints to connected subscribers.

    A PostgreSQL deployment additionally relays these through LISTEN/NOTIFY so
    that every replica observes the same hints; the payload stays identical.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[CursorNotification]]] = {}

    @asynccontextmanager
    async def subscribe(
        self, workspace_id: str
    ) -> AsyncIterator[asyncio.Queue[CursorNotification]]:
        queue: asyncio.Queue[CursorNotification] = asyncio.Queue(maxsize=MAX_QUEUED_NOTIFICATIONS)
        self._subscribers.setdefault(workspace_id, set()).add(queue)
        try:
            yield queue
        finally:
            listeners = self._subscribers.get(workspace_id)
            if listeners is not None:
                listeners.discard(queue)
                if not listeners:
                    del self._subscribers[workspace_id]

    async def publish(self, workspace_id: str, cursor: str) -> int:
        """Deliver a hint to every live subscriber and report the reach.

        A slow subscriber is skipped rather than allowed to block a push; it
        still converges because the next pull uses its own stored cursor.
        """

        notification = CursorNotification(workspace_id=workspace_id, cursor=cursor)
        delivered = 0
        for queue in tuple(self._subscribers.get(workspace_id, ())):
            try:
                queue.put_nowait(notification)
                delivered += 1
            except asyncio.QueueFull:
                continue
        return delivered

    @property
    def subscriber_count(self) -> int:
        return sum(len(listeners) for listeners in self._subscribers.values())


__all__ = ["MAX_QUEUED_NOTIFICATIONS", "CursorBroadcaster", "CursorNotification"]
