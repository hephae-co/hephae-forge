"""Firestore persistence for industry_digests collection.

Pre-synthesized national industry intelligence combining industry pulse +
tech intelligence + AI tools into a single reusable document per industry per week.

Document ID pattern: {industry_key}-{weekOf}
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "industry_digests"


async def save_industry_digest(
    industry_key: str,
    week_of: str,
    data: dict[str, Any],
) -> str:
    """Save a synthesized industry digest to Firestore. Returns document ID."""
    db = get_db()
    now = datetime.utcnow()
    doc_id = f"{industry_key}-{week_of}"

    doc_ref = db.collection(COLLECTION).document(doc_id)
    payload = {
        **data,
        "industryKey": industry_key,
        "weekOf": week_of,
        "generatedAt": now,
        "expiresAt": now + timedelta(days=7),
        "version": "1.0",
    }
    await asyncio.to_thread(doc_ref.set, payload)
    logger.info(f"[IndustryDigest] Saved {doc_id}")
    return doc_id


async def get_industry_digest(
    industry_key: str,
    week_of: str,
) -> dict[str, Any] | None:
    """Get a specific industry digest by key + week."""
    db = get_db()
    doc_id = f"{industry_key}-{week_of}"
    doc = await asyncio.to_thread(
        db.collection(COLLECTION).document(doc_id).get
    )
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    return data


async def get_latest_industry_digest(
    industry_key: str,
    week_of: str | None = None,
) -> dict[str, Any] | None:
    """Get the most recent industry digest.

    If week_of is provided, looks up by exact ID. Otherwise tries current week,
    then previous week.
    """
    db = get_db()

    if week_of:
        return await get_industry_digest(industry_key, week_of)

    # Try current week, then previous
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    for delta in [0, 7]:
        d = now - timedelta(days=delta)
        wk = f"{d.year}-W{d.isocalendar()[1]:02d}"
        result = await get_industry_digest(industry_key, wk)
        if result:
            return result

    return None
