"""Device and embedded runtime model group."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

DeviceId = NewType("DeviceId", str)


@dataclass(frozen=True, slots=True)
class DeviceHealth:
    device_id: DeviceId
    state: str
    detail: str | None = None
    battery_percent: float | None = None
    network_online: bool | None = None
