"""Firestore persistence for zipcode_profiles collection.

Stores the zipcode capability registry — a per-zipcode manifest of
data sources discovered during onboarding. Document ID is the zip code.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "zipcode_profiles"


def _deserialize_ts(data: dict[str, Any]) -> dict[str, Any]:
    """Convert Firestore timestamps to ISO strings for JSON serialization."""
    ts_fields = ("discoveredAt", "refreshAfter")
    for field in ts_fields:
        val = data.get(field)
        if val and hasattr(val, "seconds"):
            data[field] = datetime.utcfromtimestamp(
                val.seconds + val.nanoseconds / 1e9
            ).isoformat()
        elif val and hasattr(val, "isoformat"):
            data[field] = val.isoformat()
    return data


async def save_zipcode_profile(profile: dict[str, Any]) -> str:
    """Save a zipcode profile to Firestore. Returns the zip code (doc ID)."""
    db = get_db()
    zip_code = profile["zipCode"]
    doc_ref = db.collection(COLLECTION).document(zip_code)
    await asyncio.to_thread(doc_ref.set, profile)
    logger.info(f"[ZipcodeProfiles] Saved profile for {zip_code}")
    return zip_code


async def get_zipcode_profile(zip_code: str) -> dict[str, Any] | None:
    """Get a single zipcode profile by zip code."""
    db = get_db()
    doc = await asyncio.to_thread(
        db.collection(COLLECTION).document(zip_code).get
    )
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    return _deserialize_ts(data)


async def list_zipcode_profiles() -> list[dict[str, Any]]:
    """List all zipcode profiles, ordered by discovery date (newest first)."""
    db = get_db()
    query = db.collection(COLLECTION).order_by(
        "discoveredAt", direction="DESCENDING"
    )
    docs = await asyncio.to_thread(query.get)
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        results.append(_deserialize_ts(data))
    return results


async def delete_zipcode_profile(zip_code: str) -> None:
    """Delete a zipcode profile."""
    db = get_db()
    doc_ref = db.collection(COLLECTION).document(zip_code)
    await asyncio.to_thread(doc_ref.delete)
    logger.info(f"[ZipcodeProfiles] Deleted profile for {zip_code}")
