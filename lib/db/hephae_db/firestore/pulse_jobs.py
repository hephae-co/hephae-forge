"""Firestore persistence for pulse_jobs collection.

Tracks async weekly pulse generation jobs. Each document represents one
pulse generation request with status tracking.

Document ID: auto-generated
Statuses: QUEUED → RUNNING → COMPLETED | FAILED
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Literal

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

JOBS_COLLECTION = "pulse_jobs"

JobStatus = Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED"]


def _serialize_ts(data: dict[str, Any]) -> dict[str, Any]:
    """Convert Firestore timestamps to ISO strings for JSON serialization."""
    for field in ("createdAt", "startedAt", "completedAt", "timeoutAt"):
        val = data.get(field)
        if val and hasattr(val, "seconds"):
            data[field] = datetime.utcfromtimestamp(val.seconds + val.nanoseconds / 1e9).isoformat()
        elif val and hasattr(val, "isoformat"):
            data[field] = val.isoformat()
    return data


async def create_pulse_job(
    zip_code: str,
    business_type: str,
    week_of: str,
    force: bool = False,
    test_mode: bool = False,
) -> str:
    """Create a new pulse job document. Returns the job ID."""
    db = get_db()
    now = datetime.utcnow()
    doc_ref = db.collection(JOBS_COLLECTION).document()
    data: dict[str, Any] = {
        "zipCode": zip_code,
        "businessType": business_type,
        "weekOf": week_of,
        "force": force,
        "status": "QUEUED",
        "createdAt": now,
        "startedAt": None,
        "completedAt": None,
        "result": None,
        "error": None,
    }
    if test_mode:
        data["testMode"] = True
        data["expireAt"] = now + timedelta(hours=24)
    await asyncio.to_thread(doc_ref.set, data)
    logger.info(f"[PulseJobs] Created job {doc_ref.id} for {zip_code}/{business_type}{' (test)' if test_mode else ''}")
    return doc_ref.id


async def update_pulse_job(
    job_id: str,
    updates: dict[str, Any],
) -> None:
    """Update a pulse job document."""
    db = get_db()
    doc_ref = db.collection(JOBS_COLLECTION).document(job_id)
    await asyncio.to_thread(doc_ref.update, updates)


async def get_pulse_job(job_id: str) -> dict[str, Any] | None:
    """Get a pulse job by ID. Auto-fails RUNNING jobs that have timed out."""
    db = get_db()
    doc = await asyncio.to_thread(
        db.collection(JOBS_COLLECTION).document(job_id).get
    )
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id

    # Check for timeout on RUNNING jobs
    if data.get("status") == "RUNNING" and data.get("timeoutAt"):
        timeout_at = data["timeoutAt"]
        # Handle both Firestore timestamp and datetime objects
        if hasattr(timeout_at, "seconds"):
            timeout_dt = datetime.utcfromtimestamp(timeout_at.seconds + timeout_at.nanoseconds / 1e9)
        elif hasattr(timeout_at, "timestamp"):
            timeout_dt = timeout_at
        else:
            timeout_dt = None

        # Normalize both to naive UTC for comparison
        if timeout_dt:
            if hasattr(timeout_dt, "tzinfo") and timeout_dt.tzinfo is not None:
                from datetime import timezone
                timeout_dt = timeout_dt.astimezone(timezone.utc).replace(tzinfo=None)
        if timeout_dt and datetime.utcnow() > timeout_dt:
            logger.warning(f"[PulseJobs] Job {job_id} timed out — marking as FAILED")
            updates = {
                "status": "FAILED",
                "completedAt": datetime.utcnow(),
                "error": "Pipeline timeout (exceeded 15 minutes)",
            }
            await asyncio.to_thread(
                db.collection(JOBS_COLLECTION).document(job_id).update, updates
            )
            data.update(updates)

    return _serialize_ts(data)


async def list_pulse_jobs(limit: int = 20) -> list[dict[str, Any]]:
    """List recent pulse jobs (most recent first)."""
    db = get_db()
    query = (
        db.collection(JOBS_COLLECTION)
        .order_by("createdAt", direction="DESCENDING")
        .limit(limit)
    )
    docs = await asyncio.to_thread(query.get)
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        results.append(_serialize_ts(data))
    return results
