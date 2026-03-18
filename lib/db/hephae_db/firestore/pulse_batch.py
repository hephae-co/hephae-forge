"""Firestore persistence for pulse_batch_work_items collection.

Stores intermediate state for batch pulse generation. Each work item
tracks one zip code through the 5-stage batch pipeline.

Document ID pattern: {batchId}:{zipCode}
  e.g., "pulse-essex-2026-W12:07110"

Documents auto-expire after 14 days via Firestore TTL on expireAt field.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Literal

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

BATCH_COLLECTION = "pulse_batch_work_items"

WorkItemStatus = Literal[
    "QUEUED", "FETCHING", "RESEARCH", "PRE_SYNTHESIS",
    "SYNTHESIS", "CRITIQUE", "COMPLETED", "FAILED",
]


async def create_work_items(
    batch_id: str,
    zip_codes: list[str],
    business_type: str,
    week_of: str,
) -> int:
    """Create work item documents for a batch of zip codes.

    Returns the number of work items created.
    """
    db = get_db()
    now = datetime.utcnow()
    expire_at = now + timedelta(days=14)
    batch = db.batch()
    count = 0

    for zip_code in zip_codes:
        doc_id = f"{batch_id}:{zip_code}"
        doc_ref = db.collection(BATCH_COLLECTION).document(doc_id)
        batch.set(doc_ref, {
            "batchId": batch_id,
            "zipCode": zip_code,
            "businessType": business_type,
            "weekOf": week_of,
            "status": "QUEUED",
            "retryCount": 0,
            "lastError": None,
            "createdAt": now,
            "updatedAt": now,
            "expireAt": expire_at,
        })
        count += 1

    await asyncio.to_thread(batch.commit)
    logger.info(f"[PulseBatch] Created {count} work items for batch {batch_id}")
    return count


async def update_work_item(
    batch_id: str,
    zip_code: str,
    updates: dict[str, Any],
) -> None:
    """Update a work item with stage outputs or status changes."""
    db = get_db()
    doc_id = f"{batch_id}:{zip_code}"
    doc_ref = db.collection(BATCH_COLLECTION).document(doc_id)
    updates["updatedAt"] = datetime.utcnow()
    await asyncio.to_thread(doc_ref.update, updates)


async def get_work_item(
    batch_id: str,
    zip_code: str,
) -> dict[str, Any] | None:
    """Get a single work item."""
    db = get_db()
    doc_id = f"{batch_id}:{zip_code}"
    doc = await asyncio.to_thread(
        db.collection(BATCH_COLLECTION).document(doc_id).get
    )
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    return data


async def get_work_items_by_status(
    batch_id: str,
    status: WorkItemStatus,
) -> list[dict[str, Any]]:
    """Get all work items for a batch with a given status."""
    db = get_db()
    query = (
        db.collection(BATCH_COLLECTION)
        .where("batchId", "==", batch_id)
        .where("status", "==", status)
    )
    docs = await asyncio.to_thread(query.get)
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        results.append(data)
    return results


async def get_all_work_items(batch_id: str) -> list[dict[str, Any]]:
    """Get all work items for a batch."""
    db = get_db()
    query = db.collection(BATCH_COLLECTION).where("batchId", "==", batch_id)
    docs = await asyncio.to_thread(query.get)
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        results.append(data)
    return results


async def get_batch_summary(batch_id: str) -> dict[str, Any]:
    """Get a summary of batch progress (status counts)."""
    items = await get_all_work_items(batch_id)
    status_counts: dict[str, int] = {}
    for item in items:
        s = item.get("status", "UNKNOWN")
        status_counts[s] = status_counts.get(s, 0) + 1
    return {
        "batchId": batch_id,
        "totalItems": len(items),
        "statusCounts": status_counts,
        "allCompleted": all(
            i.get("status") in ("COMPLETED", "FAILED") for i in items
        ) if items else False,
    }
