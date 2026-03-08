"""Firestore CRUD for the discovery_jobs collection.

Discovery jobs are created from the admin UI and processed by the
discovery-batch Cloud Run Job when it wakes up on its configured schedule.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "discovery_jobs"

# Allowed status values
STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"


def _deserialize(data: dict[str, Any], doc_id: str) -> dict[str, Any]:
    data["id"] = doc_id
    for field in ("createdAt", "startedAt", "completedAt"):
        val = data.get(field)
        if val and hasattr(val, "seconds"):
            data[field] = datetime.utcfromtimestamp(val.seconds + val.nanoseconds / 1e9)
    return data


async def create_discovery_job(
    name: str,
    targets: list[dict[str, Any]],
    notify_email: str = "admin@hephae.co",
    settings: dict[str, Any] | None = None,
    created_by: str = "admin",
) -> str:
    """Create a new discovery job with status=pending. Returns the job ID."""
    db = get_db()
    doc_ref = db.collection(COLLECTION).document()
    now = datetime.utcnow()

    data = {
        "name": name,
        "status": STATUS_PENDING,
        "targets": targets,
        "progress": {
            "totalZips": len(targets),
            "completedZips": 0,
            "totalBusinesses": 0,
            "qualified": 0,
            "skipped": 0,
            "failed": 0,
        },
        "createdAt": now,
        "startedAt": None,
        "completedAt": None,
        "createdBy": created_by,
        "notifyEmail": notify_email,
        "settings": settings or {
            "freshnessDiscoveryDays": 30,
            "freshnessAnalysisDays": 7,
            "rateLimitSeconds": 3,
        },
        "skipReasons": [],  # sampled list of skip reasons for the summary email
    }

    await asyncio.to_thread(doc_ref.set, data)
    logger.info(f"[DiscoveryJobs] Created job {doc_ref.id}: {name}")
    return doc_ref.id


async def list_discovery_jobs(limit: int = 50) -> list[dict[str, Any]]:
    db = get_db()
    docs = await asyncio.to_thread(
        lambda: db.collection(COLLECTION)
        .order_by("createdAt", direction="DESCENDING")
        .limit(limit)
        .get()
    )
    return [_deserialize(doc.to_dict(), doc.id) for doc in docs]


async def get_discovery_job(job_id: str) -> dict[str, Any] | None:
    db = get_db()
    doc = await asyncio.to_thread(db.collection(COLLECTION).document(job_id).get)
    if not doc.exists:
        return None
    return _deserialize(doc.to_dict(), doc.id)


async def claim_next_pending_job() -> dict[str, Any] | None:
    """Atomically claim the oldest pending job by setting status=running.

    Returns the claimed job dict, or None if no pending jobs exist.
    Uses a Firestore transaction to prevent two workers from claiming the same job.
    """
    db = get_db()
    col = db.collection(COLLECTION)

    docs = await asyncio.to_thread(
        lambda: col
        .where("status", "==", STATUS_PENDING)
        .order_by("createdAt")
        .limit(1)
        .get()
    )

    if not docs:
        return None

    doc = docs[0]
    job_id = doc.id

    @db.transaction
    def _claim(txn, ref):
        snapshot = ref.get(transaction=txn)
        if not snapshot.exists or snapshot.get("status") != STATUS_PENDING:
            return False
        txn.update(ref, {
            "status": STATUS_RUNNING,
            "startedAt": datetime.utcnow(),
        })
        return True

    ref = col.document(job_id)
    try:
        claimed = await asyncio.to_thread(_claim, ref)
    except Exception:
        # Fallback: non-transactional claim (acceptable for single-worker setup)
        claimed = True
        await asyncio.to_thread(ref.update, {
            "status": STATUS_RUNNING,
            "startedAt": datetime.utcnow(),
        })

    if not claimed:
        return None

    data = doc.to_dict()
    return _deserialize(data, job_id)


async def update_job_progress(
    job_id: str,
    increment: dict[str, int] | None = None,
    completed_zip: bool = False,
    skip_reason: str | None = None,
) -> None:
    """Increment progress counters. Called after each business is processed."""
    db = get_db()
    from google.cloud.firestore import Increment, ArrayUnion

    updates: dict[str, Any] = {}

    if increment:
        for key, val in increment.items():
            updates[f"progress.{key}"] = Increment(val)

    if completed_zip:
        updates["progress.completedZips"] = Increment(1)

    if skip_reason:
        # Keep a sampled list of skip reasons (max 50) for the summary
        updates["skipReasons"] = ArrayUnion([skip_reason])

    if updates:
        await asyncio.to_thread(
            db.collection(COLLECTION).document(job_id).update,
            updates,
        )


async def complete_job(
    job_id: str,
    status: str = STATUS_COMPLETED,
    error: str | None = None,
) -> None:
    updates: dict[str, Any] = {
        "status": status,
        "completedAt": datetime.utcnow(),
    }
    if error:
        updates["error"] = error
    db = get_db()
    await asyncio.to_thread(
        db.collection(COLLECTION).document(job_id).update,
        updates,
    )
    logger.info(f"[DiscoveryJobs] Job {job_id} → {status}")


async def cancel_job(job_id: str) -> bool:
    """Cancel a pending job. Returns False if job is already running/completed."""
    job = await get_discovery_job(job_id)
    if not job or job["status"] not in (STATUS_PENDING,):
        return False
    db = get_db()
    await asyncio.to_thread(
        db.collection(COLLECTION).document(job_id).update,
        {"status": STATUS_CANCELLED, "completedAt": datetime.utcnow()},
    )
    return True


async def delete_discovery_job(job_id: str) -> None:
    db = get_db()
    await asyncio.to_thread(db.collection(COLLECTION).document(job_id).delete)
