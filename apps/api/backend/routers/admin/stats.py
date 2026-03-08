"""Dashboard stats endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from hephae_db.firestore.stats import get_dashboard_stats

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
async def stats():
    return await get_dashboard_stats()
