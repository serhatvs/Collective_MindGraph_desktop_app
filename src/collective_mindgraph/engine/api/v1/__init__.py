"""Versioned product API."""

from fastapi import APIRouter

from .data_router import router as data_router
from .job_router import router as job_router
from .live_router import router as live_router
from .memory_router import router as memory_router
from .router import router as product_router
from .system_router import router as system_router

router = APIRouter()
router.include_router(product_router)
router.include_router(data_router)
router.include_router(live_router)
router.include_router(job_router)
router.include_router(memory_router)
router.include_router(system_router)

__all__ = ["router"]
