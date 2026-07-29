"""Device enrollment, revocation, and wrapped-key custody."""

from __future__ import annotations

from typing import Any

from .authorization import AuthorizedOperations
from .contracts import Principal, Role


class DeviceService:
    """Stores device public keys and envelopes it can never unwrap."""

    def __init__(self, operations: AuthorizedOperations) -> None:
        self._operations = operations

    async def register(
        self,
        principal: Principal,
        *,
        workspace_id: str,
        device_id: str,
        name: str,
        public_key: bytes,
    ) -> None:
        """Record a device public key for an existing member."""

        async with self._operations.authorized(
            workspace_id=workspace_id,
            principal=principal,
            minimum=Role.VIEWER,
        ) as connection:
            await self._operations.members.register_device(
                connection,
                workspace_id=workspace_id,
                principal=principal,
                device_id=device_id,
                name=name,
                public_key=public_key,
                trust="trusted",
            )
            await self._operations.members.record_audit(
                connection,
                workspace_id=workspace_id,
                kind="device.registered",
                principal=principal,
                device_id=device_id,
            )

    async def revoke(
        self,
        principal: Principal,
        *,
        workspace_id: str,
        device_id: str,
    ) -> None:
        """Revoke a device and every envelope wrapped for it.

        Revocation stops future access. It cannot recall content the device
        already downloaded and decrypted.
        """

        async with self._operations.authorized(
            workspace_id=workspace_id,
            principal=principal,
            minimum=Role.ADMIN,
        ) as connection:
            await self._operations.members.revoke_device(
                connection,
                workspace_id=workspace_id,
                device_id=device_id,
            )
            await self._operations.members.record_audit(
                connection,
                workspace_id=workspace_id,
                kind="device.revoked",
                principal=principal,
                device_id=device_id,
            )

    async def store_envelope(
        self,
        principal: Principal,
        *,
        workspace_id: str,
        key_version: int,
        wrapped_key: bytes,
        recipient_device_id: str | None,
        ephemeral_public_key: bytes | None,
        salt: bytes | None,
    ) -> str:
        async with self._operations.authorized(
            workspace_id=workspace_id,
            principal=principal,
            minimum=Role.EDITOR,
        ) as connection:
            return await self._operations.members.store_envelope(
                connection,
                workspace_id=workspace_id,
                key_version=key_version,
                wrapped_key=wrapped_key,
                recipient_device_id=recipient_device_id,
                ephemeral_public_key=ephemeral_public_key,
                salt=salt,
            )

    async def envelopes_for(
        self,
        principal: Principal,
        *,
        workspace_id: str,
        device_id: str,
    ) -> tuple[Any, ...]:
        async with self._operations.authorized(
            workspace_id=workspace_id,
            principal=principal,
            minimum=Role.VIEWER,
        ) as connection:
            return await self._operations.members.envelopes_for_device(
                connection,
                workspace_id=workspace_id,
                device_id=device_id,
            )


__all__ = ["DeviceService"]
