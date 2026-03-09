"""Heartbeat monitoring — persistent business capability watches.

Each heartbeat watches a specific business for a specific user,
running selected capabilities on a weekly schedule and tracking
whether anything changed since the last run.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "heartbeats"


def _next_weekday(day_of_week: int, hour: int = 13) -> datetime:
    """Compute the next occurrence of *day_of_week* (0=Mon … 6=Sun) at *hour* UTC.

    8 AM ET ≈ 13:00 UTC (during EST; 12:00 during EDT — we use 13 as a
    safe default so the run never fires before 8 AM ET).
    """
    now = datetime.now(timezone.utc)
    days_ahead = day_of_week - now.weekday()
    if days_ahead <= 0:  # target day already passed this week
        days_ahead += 7
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)
    return target


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def create_heartbeat(
    uid: str,
    business_slug: str,
    business_name: str,
    capabilities: list[str],
    day_of_week: int = 1,
) -> str:
    """Create a new heartbeat watch.  Returns the document ID.

    One heartbeat per user per business — if one already exists the
    existing document ID is returned instead of creating a duplicate.
    """
    db = get_db()
    col = db.collection(COLLECTION)

    # Deduplicate: one heartbeat per user+business
    existing = await asyncio.to_thread(
        lambda: col
        .where("uid", "==", uid)
        .where("businessSlug", "==", business_slug)
        .limit(1)
        .get()
    )
    if existing:
        existing_id = existing[0].id
        logger.info(
            "Heartbeat already exists for uid=%s business=%s — returning %s",
            uid, business_slug, existing_id,
        )
        return existing_id

    doc_ref = col.document()
    now = datetime.now(timezone.utc)

    heartbeat_data: dict[str, Any] = {
        "uid": uid,
        "businessSlug": business_slug,
        "businessName": business_name,
        "capabilities": capabilities,
        "frequency": "weekly",
        "dayOfWeek": day_of_week,
        "active": True,
        "createdAt": now,
        "lastRunAt": None,
        "nextRunAfter": _next_weekday(day_of_week),
        "lastSnapshot": {},
        "totalRuns": 0,
        "consecutiveOks": 0,
    }

    await asyncio.to_thread(doc_ref.set, heartbeat_data)
    logger.info(
        "Created heartbeat %s for uid=%s business=%s caps=%s",
        doc_ref.id, uid, business_slug, capabilities,
    )
    return doc_ref.id


async def get_user_heartbeats(uid: str) -> list[dict]:
    """List all heartbeats for a user."""
    db = get_db()
    docs = await asyncio.to_thread(
        lambda: db.collection(COLLECTION)
        .where("uid", "==", uid)
        .order_by("createdAt")
        .get()
    )
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        results.append(data)
    return results


async def get_heartbeat(heartbeat_id: str) -> dict | None:
    """Get a single heartbeat by ID."""
    db = get_db()
    doc = await asyncio.to_thread(
        db.collection(COLLECTION).document(heartbeat_id).get,
    )
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    return data


async def update_heartbeat(heartbeat_id: str, updates: dict) -> None:
    """Update heartbeat fields (capabilities, active, dayOfWeek, etc).

    If *dayOfWeek* is changed, *nextRunAfter* is automatically recomputed.
    """
    if "dayOfWeek" in updates:
        updates["nextRunAfter"] = _next_weekday(updates["dayOfWeek"])

    db = get_db()
    await asyncio.to_thread(
        db.collection(COLLECTION).document(heartbeat_id).update,
        updates,
    )


async def delete_heartbeat(heartbeat_id: str) -> None:
    """Delete a heartbeat."""
    db = get_db()
    await asyncio.to_thread(
        db.collection(COLLECTION).document(heartbeat_id).delete,
    )
    logger.info("Deleted heartbeat %s", heartbeat_id)


# ---------------------------------------------------------------------------
# Scheduler helpers
# ---------------------------------------------------------------------------

async def get_due_heartbeats(now: datetime) -> list[dict]:
    """Get all heartbeats where nextRunAfter <= *now* AND active is True."""
    db = get_db()
    docs = await asyncio.to_thread(
        lambda: db.collection(COLLECTION)
        .where("active", "==", True)
        .where("nextRunAfter", "<=", now)
        .order_by("nextRunAfter")
        .get()
    )
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        results.append(data)
    return results


async def record_heartbeat_run(
    heartbeat_id: str,
    snapshot: dict,
    next_run: datetime,
) -> None:
    """Record a completed heartbeat run.

    Updates lastRunAt, lastSnapshot, nextRunAfter, and increments totalRuns.
    If the snapshot contains no significant deltas (``deltas`` key is empty
    or missing), *consecutiveOks* is incremented; otherwise it resets to 0.
    """
    from google.cloud.firestore_v1 import Increment

    now = datetime.now(timezone.utc)
    has_deltas = bool(snapshot.get("deltas"))

    db = get_db()
    doc_ref = db.collection(COLLECTION).document(heartbeat_id)

    updates: dict[str, Any] = {
        "lastRunAt": now,
        "lastSnapshot": snapshot,
        "nextRunAfter": next_run,
        "totalRuns": Increment(1),
    }

    if has_deltas:
        updates["consecutiveOks"] = 0
    else:
        updates["consecutiveOks"] = Increment(1)

    await asyncio.to_thread(doc_ref.update, updates)
    logger.info(
        "Recorded heartbeat run for %s — deltas=%s nextRun=%s",
        heartbeat_id, has_deltas, next_run,
    )
