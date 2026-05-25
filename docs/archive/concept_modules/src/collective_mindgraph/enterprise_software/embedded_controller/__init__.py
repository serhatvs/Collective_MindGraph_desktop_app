"""Embedded controller service submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.enterprise_software.models import DeviceHealth, DeviceId


class EmbeddedController(Protocol):
    """Manages lifecycle and configuration of embedded hardware."""

    def start(self, device_id: DeviceId) -> None:
        """Start device operations."""

    def stop(self, device_id: DeviceId) -> None:
        """Stop device operations."""

    def health(self, device_id: DeviceId) -> DeviceHealth:
        """Return device health."""
