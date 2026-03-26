"""Firestore persistence for zipcode_interest collection.

Tracks zip codes submitted by users who want ultralocal coverage.

Document ID pattern: auto-generated
Collection: zipcode_interest
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "zipcode_interest"


async def save_zipcode_interest(
    zip_code: str,
    business_type: str | None = None,
    email: str | None = None,
    city: str | None = None,
    state: str | None = None,
) -> str:
    """Save a zipcode interest submission. Returns the new doc ID."""
    db = get_db()
    now = datetime.utcnow()

    data: dict[str, Any] = {
        "zipCode": zip_code,
        "submittedAt": now,
        "status": "pending",
    }
    if business_type:
        data["businessType"] = business_type
    if email:
        data["email"] = email
    if city:
        data["city"] = city
    if state:
        data["state"] = state

    doc_ref = await asyncio.to_thread(
        db.collection(COLLECTION).add, data
    )
    doc_id = doc_ref[1].id
    logger.info(f"[ZipcodeInterest] Saved interest for {zip_code} → {doc_id}")
    return doc_id


async def get_interest_count(zip_code: str) -> int:
    """Return how many interest submissions exist for a zip code."""
    db = get_db()
    query = db.collection(COLLECTION).where("zipCode", "==", zip_code)
    docs = await asyncio.to_thread(query.get)
    return len(docs)
