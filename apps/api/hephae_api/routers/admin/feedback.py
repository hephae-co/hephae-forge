"""Admin feedback endpoint — quality scoring dashboard.

GET /api/admin/feedback  — summary + raw items, filterable by dataType/vertical/businessSlug.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from hephae_api.lib.auth import verify_admin_request

router = APIRouter(
    prefix="/api/admin/feedback",
    tags=["feedback-admin"],
    dependencies=[Depends(verify_admin_request)],
)


@router.get("")
async def get_feedback(
    dataType: str | None = Query(None),
    vertical: str | None = Query(None),
    businessSlug: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Return feedback summary + raw items.

    Summary includes: upCount, downCount, totalCount, helpfulPct, topTags.
    Items are ordered by createdAt descending.
    """
    from hephae_db.firestore.user_feedback import get_feedback_summary

    return await get_feedback_summary(
        data_type=dataType,
        vertical=vertical,
        business_slug=businessSlug,
        limit=limit,
        offset=offset,
    )
