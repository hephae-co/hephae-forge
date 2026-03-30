"""Firestore persistence for weekly_digests collection.

Pre-synthesized weekly briefings per zip code + business type. Each digest
combines zip pulse + industry pulse + tech intelligence + cached signals
into a single reusable document.

Document ID pattern: {zip_code}-{business_type_slug}-{weekOf}
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Any

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "weekly_digests"


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower().strip()).strip("-")


def _make_doc_id(zip_code: str, business_type: str, week_of: str) -> str:
    return f"{zip_code}-{_slugify(business_type)}-{week_of}"


async def save_weekly_digest(
    zip_code: str,
    business_type: str,
    week_of: str,
    data: dict[str, Any],
) -> str:
    """Save a synthesized weekly digest to Firestore. Returns document ID."""
    db = get_db()
    now = datetime.utcnow()
    doc_id = _make_doc_id(zip_code, business_type, week_of)

    doc_ref = db.collection(COLLECTION).document(doc_id)
    payload = {
        **data,
        "zipCode": zip_code,
        "businessType": business_type,
        "weekOf": week_of,
        "generatedAt": now,
        "expiresAt": now + timedelta(days=7),
        "version": "1.0",
    }
    await asyncio.to_thread(doc_ref.set, payload)
    logger.info(f"[WeeklyDigest] Saved {doc_id}")
    return doc_id


async def get_weekly_digest(
    zip_code: str,
    business_type: str,
    week_of: str,
) -> dict[str, Any] | None:
    """Get a specific weekly digest by zip + business type + week."""
    db = get_db()
    doc_id = _make_doc_id(zip_code, business_type, week_of)
    doc = await asyncio.to_thread(
        db.collection(COLLECTION).document(doc_id).get
    )
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    return data


async def get_latest_weekly_digest(
    zip_code: str,
    business_type: str,
    week_of: str | None = None,
) -> dict[str, Any] | None:
    """Get the most recent weekly digest for a zip + business type.

    If week_of is provided, looks up by exact ID. Otherwise tries current week,
    then previous week.
    """
    if week_of:
        return await get_weekly_digest(zip_code, business_type, week_of)

    # Try current week, then previous
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    for delta in [0, 7]:
        d = now - timedelta(days=delta)
        wk = f"{d.year}-W{d.isocalendar()[1]:02d}"
        result = await get_weekly_digest(zip_code, business_type, wk)
        if result:
            return result

    return None
