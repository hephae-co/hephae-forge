"""Firestore persistence for registered_zipcodes collection.

Tracks zip codes registered for weekly pulse generation.
Business types are stored as a list on each zip doc for pulse iteration.

Document ID pattern: {zipCode} (e.g., "07110")
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "registered_zipcodes"


def _next_monday() -> datetime:
    """Return the next Monday at 06:00 ET (11:00 UTC)."""
    now = datetime.utcnow()
    days_ahead = (7 - now.weekday()) % 7  # Monday is 0
    if days_ahead == 0:
        days_ahead = 7
    next_mon = now.replace(hour=11, minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)
    return next_mon


def _deserialize_ts(data: dict[str, Any]) -> dict[str, Any]:
    """Convert Firestore timestamps to ISO strings for JSON serialization."""
    ts_fields = ("registeredAt", "lastPulseAt", "nextScheduledAt", "onboardedAt")
    for field in ts_fields:
        val = data.get(field)
        if val and hasattr(val, "seconds"):
            data[field] = datetime.utcfromtimestamp(val.seconds + val.nanoseconds / 1e9).isoformat()
        elif val and hasattr(val, "isoformat"):
            data[field] = val.isoformat()
    return data


async def register_zipcode(
    zip_code: str,
    city: str,
    state: str,
    county: str,
) -> str:
    """Register a zipcode for weekly pulse generation. Returns doc ID."""
    db = get_db()
    doc_id = zip_code
    now = datetime.utcnow()

    doc_ref = db.collection(COLLECTION).document(doc_id)
    data = {
        "zipCode": zip_code,
        "businessTypes": ["Restaurants"],
        "city": city,
        "state": state,
        "county": county,
        "status": "active",
        "onboardingStatus": "onboarding",
        "onboardedAt": None,
        "registeredAt": now,
        "lastPulseAt": None,
        "lastPulseId": None,
        "lastPulseHeadline": "",
        "lastPulseInsightCount": 0,
        "pulseCount": 0,
        "nextScheduledAt": _next_monday(),
        "createdBy": "admin",
    }
    await asyncio.to_thread(doc_ref.set, data)
    logger.info(f"[RegisteredZips] Registered {doc_id} ({city}, {state})")
    return doc_id


async def unregister_zipcode(zip_code: str) -> None:
    """Delete a registered zipcode entry."""
    db = get_db()
    doc_ref = db.collection(COLLECTION).document(zip_code)
    await asyncio.to_thread(doc_ref.delete)
    logger.info(f"[RegisteredZips] Unregistered {zip_code}")


async def pause_zipcode(zip_code: str) -> None:
    """Pause weekly pulse generation for a zipcode."""
    db = get_db()
    doc_ref = db.collection(COLLECTION).document(zip_code)
    await asyncio.to_thread(doc_ref.update, {"status": "paused"})
    logger.info(f"[RegisteredZips] Paused {zip_code}")


async def resume_zipcode(zip_code: str) -> None:
    """Resume weekly pulse generation for a zipcode."""
    db = get_db()
    doc_ref = db.collection(COLLECTION).document(zip_code)
    await asyncio.to_thread(doc_ref.update, {
        "status": "active",
        "nextScheduledAt": _next_monday(),
    })
    logger.info(f"[RegisteredZips] Resumed {zip_code}")


async def list_registered_zipcodes(status: str | None = None) -> list[dict[str, Any]]:
    """List all registered zipcodes, optionally filtered by status."""
    db = get_db()
    query = db.collection(COLLECTION).order_by("registeredAt", direction="DESCENDING")
    if status:
        query = query.where("status", "==", status)

    docs = await asyncio.to_thread(query.get)
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        results.append(_deserialize_ts(data))
    return results


async def get_registered_zipcode(zip_code: str) -> dict[str, Any] | None:
    """Get a single registered zipcode entry."""
    db = get_db()
    doc = await asyncio.to_thread(
        db.collection(COLLECTION).document(zip_code).get
    )
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    return _deserialize_ts(data)


async def approve_zipcode(zip_code: str) -> None:
    """Mark zipcode as onboarded (human or auto approval)."""
    db = get_db()
    doc_ref = db.collection(COLLECTION).document(zip_code)
    now = datetime.utcnow()
    await asyncio.to_thread(doc_ref.update, {
        "onboardingStatus": "onboarded",
        "onboardedAt": now,
    })
    logger.info(f"[RegisteredZips] Approved (onboarded) {zip_code}")


async def update_last_pulse(
    zip_code: str,
    pulse_id: str,
    headline: str = "",
    insight_count: int = 0,
) -> None:
    """Update lastPulseAt, lastPulseId, headline, insight count, increment pulseCount, set next schedule."""
    db = get_db()
    doc_ref = db.collection(COLLECTION).document(zip_code)
    from google.cloud.firestore_v1 import Increment

    now = datetime.utcnow()
    await asyncio.to_thread(doc_ref.update, {
        "lastPulseAt": now,
        "lastPulseId": pulse_id,
        "lastPulseHeadline": headline,
        "lastPulseInsightCount": insight_count,
        "pulseCount": Increment(1),
        "nextScheduledAt": _next_monday(),
    })
    logger.info(f"[RegisteredZips] Updated last pulse for {zip_code} -> {pulse_id}")


async def add_business_type(zip_code: str, business_type: str) -> None:
    """Add a business type to a registered zipcode's list."""
    from google.cloud.firestore_v1 import ArrayUnion

    db = get_db()
    doc_ref = db.collection(COLLECTION).document(zip_code)
    await asyncio.to_thread(doc_ref.update, {
        "businessTypes": ArrayUnion([business_type]),
    })
    logger.info(f"[RegisteredZips] Added business type '{business_type}' to {zip_code}")


async def remove_business_type(zip_code: str, business_type: str) -> None:
    """Remove a business type from a registered zipcode's list."""
    from google.cloud.firestore_v1 import ArrayRemove

    db = get_db()
    doc_ref = db.collection(COLLECTION).document(zip_code)
    await asyncio.to_thread(doc_ref.update, {
        "businessTypes": ArrayRemove([business_type]),
    })
    logger.info(f"[RegisteredZips] Removed business type '{business_type}' from {zip_code}")
