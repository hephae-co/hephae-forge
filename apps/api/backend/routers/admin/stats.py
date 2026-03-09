"""Dashboard stats endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.lib.auth import verify_admin_request

from hephae_db.firestore.stats import get_dashboard_stats

router = APIRouter(prefix="/api/stats", tags=["stats"], dependencies=[Depends(verify_admin_request)])


@router.get("")
async def stats():
    return await get_dashboard_stats()
