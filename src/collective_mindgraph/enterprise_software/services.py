"""Public service boundary for embedded and enterprise runtime workflows."""

from __future__ import annotations

from typing import Protocol

from .models import DeviceHealth, DeviceId


class EnterpriseRuntimeService(Protocol):
    """Coordinates devices without importing meeting or assistant internals."""

    def health(self, device_id: DeviceId) -> DeviceHealth:
        """Return current device status."""

    def send_audio_for_processing(self, device_id: DeviceId, audio_uri: str) -> str:
        """Send captured audio through a configured processing transport."""
