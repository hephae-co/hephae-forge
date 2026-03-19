"""Firestore persistence for registered_zipcodes collection.

Tracks zip code + business type pairs registered for weekly pulse generation.
The cron system uses this collection to determine which pulses to auto-generate.

Document ID pattern: {zipCode}-{businessType_slug} (e.g., "07110-restaurants")
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Any

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "registered_zipcodes"


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower().strip()).strip("-")


def _doc_id(zip_code: str, business_type: str) -> str:
    return f"{zip_code}-{_slugify(business_type)}"


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
    ts_fields = ("registeredAt", "lastPulseAt", "nextScheduledAt")
    for field in ts_fields:
        val = data.get(field)
        if val and hasattr(val, "seconds"):
            data[field] = datetime.utcfromtimestamp(val.seconds + val.nanoseconds / 1e9).isoformat()
        elif val and hasattr(val, "isoformat"):
            data[field] = val.isoformat()
    return data


async def register_zipcode(
    zip_code: str,
    business_type: str,
    city: str,
    state: str,
    county: str,
) -> str:
    """Register a zipcode + business type for weekly pulse generation. Returns doc ID."""
    db = get_db()
    doc_id = _doc_id(zip_code, business_type)
    now = datetime.utcnow()

    doc_ref = db.collection(COLLECTION).document(doc_id)
    data = {
        "zipCode": zip_code,
        "businessType": business_type,
        "city": city,
        "state": state,
        "county": county,
        "status": "active",
        "registeredAt": now,
        "lastPulseAt": None,
        "lastPulseId": None,
        "pulseCount": 0,
        "nextScheduledAt": _next_monday(),
        "createdBy": "admin",
    }
    await asyncio.to_thread(doc_ref.set, data)
    logger.info(f"[RegisteredZips] Registered {doc_id} ({city}, {state})")
    return doc_id


async def unregister_zipcode(zip_code: str, business_type: str) -> None:
    """Delete a registered zipcode entry."""
    db = get_db()
    doc_id = _doc_id(zip_code, business_type)
    doc_ref = db.collection(COLLECTION).document(doc_id)
    await asyncio.to_thread(doc_ref.delete)
    logger.info(f"[RegisteredZips] Unregistered {doc_id}")


async def pause_zipcode(zip_code: str, business_type: str) -> None:
    """Pause weekly pulse generation for a zipcode."""
    db = get_db()
    doc_id = _doc_id(zip_code, business_type)
    doc_ref = db.collection(COLLECTION).document(doc_id)
    await asyncio.to_thread(doc_ref.update, {"status": "paused"})
    logger.info(f"[RegisteredZips] Paused {doc_id}")


async def resume_zipcode(zip_code: str, business_type: str) -> None:
    """Resume weekly pulse generation for a zipcode."""
    db = get_db()
    doc_id = _doc_id(zip_code, business_type)
    doc_ref = db.collection(COLLECTION).document(doc_id)
    await asyncio.to_thread(doc_ref.update, {
        "status": "active",
        "nextScheduledAt": _next_monday(),
    })
    logger.info(f"[RegisteredZips] Resumed {doc_id}")


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


async def get_registered_zipcode(zip_code: str, business_type: str) -> dict[str, Any] | None:
    """Get a single registered zipcode entry."""
    db = get_db()
    doc_id = _doc_id(zip_code, business_type)
    doc = await asyncio.to_thread(
        db.collection(COLLECTION).document(doc_id).get
    )
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    return _deserialize_ts(data)


async def update_last_pulse(
    zip_code: str,
    business_type: str,
    pulse_id: str,
) -> None:
    """Update lastPulseAt, lastPulseId, increment pulseCount, set next schedule."""
    db = get_db()
    doc_id = _doc_id(zip_code, business_type)
    doc_ref = db.collection(COLLECTION).document(doc_id)
    from google.cloud.firestore_v1 import Increment

    now = datetime.utcnow()
    await asyncio.to_thread(doc_ref.update, {
        "lastPulseAt": now,
        "lastPulseId": pulse_id,
        "pulseCount": Increment(1),
        "nextScheduledAt": _next_monday(),
    })
    logger.info(f"[RegisteredZips] Updated last pulse for {doc_id} → {pulse_id}")
