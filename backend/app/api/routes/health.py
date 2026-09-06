from __future__ import annotations

"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    """Service health check."""
    from app.infrastructure.database import get_pool

    pool = get_pool()
    db_status = "UP" if pool else "DOWN"

    return {
        "status": "UP",
        "service": "moveiq",
        "version": "0.1.0",
        "database": {"status": db_status},
    }
