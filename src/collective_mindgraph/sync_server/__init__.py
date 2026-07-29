"""Opaque, content-free synchronization service.

The service stores sealed bytes plus bounded routing and audit metadata. It
never holds workspace keys, device private keys, recovery codes, or search
indexes, so it cannot decrypt anything it stores.
"""

from .settings import SyncServerSettings, get_sync_server_settings

__all__ = ["SyncServerSettings", "get_sync_server_settings"]
