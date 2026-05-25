"""Status display service submodule."""

from __future__ import annotations

from typing import Protocol

from collective_mindgraph.enterprise_software.models import DeviceHealth


class StatusDisplay(Protocol):
    """Displays processing, network, and device state."""

    def show(self, health: DeviceHealth, message: str | None = None) -> None:
        """Update the physical or software status display."""
