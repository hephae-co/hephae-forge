"""Firestore persistence for research_digests collection.

Synthesized research landscape per vertical per week — combines research
references, citations, guides, and external studies into a structured digest.

Document ID pattern: {vertical}-{weekOf}
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "research_digests"


async def save_research_digest(vertical: str, week_of: str, data: dict[str, Any]) -> str:
    db = get_db()
    now = datetime.utcnow()
    doc_id = f"{vertical}-{week_of}"
    payload = {**data, "vertical": vertical, "weekOf": week_of, "generatedAt": now, "expiresAt": now + timedelta(days=14), "version": "1.0"}
    await asyncio.to_thread(db.collection(COLLECTION).document(doc_id).set, payload)
    logger.info(f"[ResearchDigest] Saved {doc_id}")
    return doc_id


async def get_research_digest(vertical: str, week_of: str) -> dict[str, Any] | None:
    db = get_db()
    doc = await asyncio.to_thread(db.collection(COLLECTION).document(f"{vertical}-{week_of}").get)
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    return data


async def get_latest_research_digest(vertical: str) -> dict[str, Any] | None:
    from datetime import timedelta
    now = datetime.utcnow()
    for delta in [0, 7, 14]:
        d = now - timedelta(days=delta)
        wk = f"{d.year}-W{d.isocalendar()[1]:02d}"
        result = await get_research_digest(vertical, wk)
        if result:
            return result
    return None
