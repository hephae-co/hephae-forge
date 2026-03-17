"""Firestore persistence for zipcode_weekly_pulse collection.

Stores weekly briefings per zip code + business type. Each document represents
one week's pulse for a specific zip/business-type pair.

Document ID pattern: {zip_code}-{business_type_slug}-{YYYYMMDD}
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import Any

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

PULSE_COLLECTION = "zipcode_weekly_pulse"


def _deserialize_ts(data: dict[str, Any], fields: list[str]) -> None:
    """In-place convert Firestore timestamps to datetime."""
    for field in fields:
        val = data.get(field)
        if val and hasattr(val, "seconds"):
            data[field] = datetime.utcfromtimestamp(val.seconds + val.nanoseconds / 1e9)


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower().strip()).strip("-")


def generate_pulse_id(zip_code: str, business_type: str, week_of: str = "") -> str:
    """Generate a document ID for a weekly pulse.

    Args:
        zip_code: The zip code.
        business_type: Business category (e.g. "Restaurants").
        week_of: ISO date string (YYYY-MM-DD). Defaults to today.
    """
    if not week_of:
        week_of = datetime.utcnow().strftime("%Y-%m-%d")
    date_slug = week_of.replace("-", "")
    return f"{zip_code}-{_slugify(business_type)}-{date_slug}"


async def save_weekly_pulse(
    zip_code: str,
    business_type: str,
    week_of: str,
    pulse: dict[str, Any],
    signals_used: list[str] | None = None,
) -> str:
    """Save a weekly pulse briefing to Firestore.

    Returns the document ID.
    """
    db = get_db()
    now = datetime.utcnow()
    doc_id = generate_pulse_id(zip_code, business_type, week_of)

    doc_ref = db.collection(PULSE_COLLECTION).document(doc_id)
    data = {
        "zipCode": zip_code,
        "businessType": business_type,
        "weekOf": week_of,
        "pulse": pulse,
        "signalsUsed": signals_used or [],
        "createdAt": now,
        "updatedAt": now,
    }
    await asyncio.to_thread(doc_ref.set, data)
    logger.info(f"[WeeklyPulse] Saved pulse {doc_id}")
    return doc_id


async def get_latest_pulse(
    zip_code: str,
    business_type: str,
) -> dict[str, Any] | None:
    """Get the most recent pulse for a zip code + business type."""
    db = get_db()
    query = (
        db.collection(PULSE_COLLECTION)
        .where("zipCode", "==", zip_code)
        .where("businessType", "==", business_type)
        .order_by("createdAt", direction="DESCENDING")
        .limit(1)
    )
    docs = await asyncio.to_thread(query.get)
    if not docs:
        return None
    data = docs[0].to_dict()
    data["id"] = docs[0].id
    _deserialize_ts(data, ["createdAt", "updatedAt"])
    return data


async def get_pulse_history(
    zip_code: str,
    business_type: str,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Get historical pulses for a zip code + business type (most recent first)."""
    db = get_db()
    query = (
        db.collection(PULSE_COLLECTION)
        .where("zipCode", "==", zip_code)
        .where("businessType", "==", business_type)
        .order_by("createdAt", direction="DESCENDING")
        .limit(limit)
    )
    docs = await asyncio.to_thread(query.get)
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        _deserialize_ts(data, ["createdAt", "updatedAt"])
        results.append(data)
    return results


async def get_pulse_by_id(pulse_id: str) -> dict[str, Any] | None:
    """Get a specific pulse by document ID."""
    db = get_db()
    doc = await asyncio.to_thread(
        db.collection(PULSE_COLLECTION).document(pulse_id).get
    )
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    _deserialize_ts(data, ["createdAt", "updatedAt"])
    return data


async def list_pulses(limit: int = 20) -> list[dict[str, Any]]:
    """List all recent pulses across all zip codes."""
    db = get_db()
    query = (
        db.collection(PULSE_COLLECTION)
        .order_by("createdAt", direction="DESCENDING")
        .limit(limit)
    )
    docs = await asyncio.to_thread(query.get)
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        _deserialize_ts(data, ["createdAt", "updatedAt"])
        # Return summary without full pulse data
        pulse = data.get("pulse", {})
        results.append({
            "id": data["id"],
            "zipCode": data.get("zipCode", ""),
            "businessType": data.get("businessType", ""),
            "weekOf": data.get("weekOf", ""),
            "headline": pulse.get("headline", ""),
            "insightCount": len(pulse.get("insights", [])),
            "createdAt": data.get("createdAt"),
        })
    return results


async def delete_pulse(pulse_id: str) -> None:
    """Delete a pulse by document ID."""
    db = get_db()
    await asyncio.to_thread(
        db.collection(PULSE_COLLECTION).document(pulse_id).delete
    )
