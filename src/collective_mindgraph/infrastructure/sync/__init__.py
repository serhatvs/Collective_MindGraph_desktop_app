"""Adapters that carry sealed bytes to and from the synchronization service."""

from .http_transport import HttpSyncTransport

__all__ = ["HttpSyncTransport"]
