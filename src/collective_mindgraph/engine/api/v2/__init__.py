"""Localhost surface for functionality the legacy v1 contracts do not cover."""

from .collaboration_router import router as collaboration_router
from .knowledge_router import router as knowledge_router
from .sync_router import router as sync_router

__all__ = ["collaboration_router", "knowledge_router", "sync_router"]
