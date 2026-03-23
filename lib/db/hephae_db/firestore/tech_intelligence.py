"""Firestore persistence for tech_intelligence collection.

Stores weekly technology landscape profiles per industry vertical.
Document ID: {vertical}-{weekOf} (e.g., barber-2026-W12)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "tech_intelligence"


async def get_tech_intelligence(vertical: str, week_of: str) -> dict[str, Any] | None:
    """Get tech intelligence for a vertical + week."""
    db = get_db()
    doc_id = f"{vertical}-{week_of}"
    doc = await asyncio.to_thread(
        db.collection(COLLECTION).document(doc_id).get
    )
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    return data


async def save_tech_intelligence(
    vertical: str,
    week_of: str,
    profile: dict[str, Any],
) -> str:
    """Save tech intelligence profile for a vertical + week."""
    db = get_db()
    doc_id = f"{vertical}-{week_of}"
    doc_ref = db.collection(COLLECTION).document(doc_id)

    data = {
        "vertical": vertical,
        "weekOf": week_of,
        "generatedAt": datetime.utcnow(),
        **profile,
    }

    await asyncio.to_thread(doc_ref.set, data)
    logger.info(f"[TechIntelligence] Saved {doc_id}")
    return doc_id


async def list_tech_intelligence(vertical: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
    """List recent tech intelligence profiles.

    Uses simple filters without order_by to avoid composite index requirements.
    """
    db = get_db()
    if vertical:
        query = db.collection(COLLECTION).where("vertical", "==", vertical)
    else:
        query = db.collection(COLLECTION)

    docs = await asyncio.to_thread(query.get)
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        results.append(data)
    results.sort(key=lambda x: str(x.get("generatedAt", "")), reverse=True)
    results = results[:limit]
    return results
