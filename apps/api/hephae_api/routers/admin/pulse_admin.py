"""Admin endpoints for pulse batch monitoring.

Separate from the existing weekly_pulse.py admin router which handles
single-pulse operations. This file handles batch-specific operations.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from hephae_api.lib.auth import verify_admin_request

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/weekly-pulse/batches",
    tags=["pulse-admin"],
    dependencies=[Depends(verify_admin_request)],
)


@router.get("")
async def list_batches(limit: int = 20):
    """List recent pulse batches with summary stats.

    Queries pulse_batch_work_items grouped by batchId.
    """
    from hephae_common.firebase import get_db
    import asyncio

    db = get_db()
    # Get distinct batch IDs from recent work items
    query = (
        db.collection("pulse_batch_work_items")
        .order_by("createdAt", direction="DESCENDING")
        .limit(limit * 5)  # Get more items to find distinct batches
    )
    docs = await asyncio.to_thread(query.get)

    # Group by batchId
    batches: dict[str, dict] = {}
    for doc in docs:
        data = doc.to_dict()
        bid = data.get("batchId", "")
        if bid not in batches:
            batches[bid] = {
                "batchId": bid,
                "businessType": data.get("businessType", ""),
                "weekOf": data.get("weekOf", ""),
                "totalItems": 0,
                "completed": 0,
                "failed": 0,
                "createdAt": data.get("createdAt"),
            }
        batches[bid]["totalItems"] += 1
        status = data.get("status", "")
        if status == "COMPLETED":
            batches[bid]["completed"] += 1
        elif status == "FAILED":
            batches[bid]["failed"] += 1

    result = sorted(batches.values(), key=lambda b: str(b.get("createdAt", "")), reverse=True)
    return result[:limit]


@router.get("/{batch_id}")
async def get_batch_detail(batch_id: str):
    """Get detailed status for a specific batch."""
    from hephae_db.firestore.pulse_batch import get_batch_summary, get_all_work_items

    summary = await get_batch_summary(batch_id)
    items = await get_all_work_items(batch_id)

    # Return summary + per-zip status (without full signal data)
    zip_statuses = []
    for item in items:
        zip_statuses.append({
            "zipCode": item.get("zipCode", ""),
            "status": item.get("status", ""),
            "lastError": item.get("lastError"),
            "hasSignals": bool(item.get("rawSignals")),
            "hasSynthesis": bool(item.get("synthesisOutput")),
            "critiquePass": (item.get("critiqueResult") or {}).get("overall_pass"),
        })

    return {
        **summary,
        "items": sorted(zip_statuses, key=lambda z: z["zipCode"]),
    }
