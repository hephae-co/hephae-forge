"""Firestore persistence for QA test runs.

Collection: test_runs
TTL: Documents older than 7 days are deleted on list/read via lazy cleanup.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)

COLLECTION = "test_runs"
TTL_DAYS = 7


async def save_test_run(summary: dict[str, Any]) -> str:
    """Persist a test run summary to Firestore. Returns the document ID."""
    from hephae_common.firebase import get_db

    db = get_db()
    doc_ref = db.collection(COLLECTION).document(summary["runId"])
    data = {
        **summary,
        "createdAt": datetime.now(timezone.utc),
    }
    await asyncio.to_thread(doc_ref.set, data)
    logger.info(f"[TestRuns] Saved run {summary['runId']}")
    return summary["runId"]


async def list_test_runs(limit: int = 20) -> list[dict[str, Any]]:
    """List recent test runs, newest first. Triggers lazy TTL cleanup."""
    from hephae_common.firebase import get_db

    db = get_db()

    # Lazy TTL cleanup — delete docs older than 7 days
    asyncio.create_task(_cleanup_expired_runs(db))

    query = (
        db.collection(COLLECTION)
        .order_by("createdAt", direction="DESCENDING")
        .limit(limit)
    )
    docs = await asyncio.to_thread(query.get)
    results = []
    for doc in docs:
        data = doc.to_dict()
        if data:
            # Serialize datetime fields
            for field in ("createdAt",):
                val = data.get(field)
                if val and hasattr(val, "isoformat"):
                    data[field] = val.isoformat()
            results.append(data)
    return results


async def get_test_run(run_id: str) -> dict[str, Any] | None:
    """Get a single test run by ID."""
    from hephae_common.firebase import get_db

    db = get_db()
    doc = await asyncio.to_thread(db.collection(COLLECTION).document(run_id).get)
    if doc.exists:
        data = doc.to_dict()
        for field in ("createdAt",):
            val = data.get(field)
            if val and hasattr(val, "isoformat"):
                data[field] = val.isoformat()
        return data
    return None


async def _cleanup_expired_runs(db) -> None:
    """Delete test runs older than TTL_DAYS. Runs as background task."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=TTL_DAYS)
        query = (
            db.collection(COLLECTION)
            .where("createdAt", "<", cutoff)
            .limit(100)
        )
        docs = await asyncio.to_thread(query.get)
        if not docs:
            return

        batch = db.batch()
        count = 0
        for doc in docs:
            batch.delete(doc.reference)
            count += 1

        if count > 0:
            await asyncio.to_thread(batch.commit)
            logger.info(f"[TestRuns] TTL cleanup: deleted {count} expired run(s)")
    except Exception as e:
        logger.warning(f"[TestRuns] TTL cleanup failed: {e}")
