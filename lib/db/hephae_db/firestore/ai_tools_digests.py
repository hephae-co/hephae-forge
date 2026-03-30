"""Firestore persistence for ai_tools_digests collection.

Synthesized AI tools landscape per vertical per week — combines the ai_tools
catalog, tech_intelligence, and research references into a structured digest.

Document ID pattern: {vertical}-{weekOf}
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "ai_tools_digests"


async def save_ai_tools_digest(vertical: str, week_of: str, data: dict[str, Any]) -> str:
    db = get_db()
    now = datetime.utcnow()
    doc_id = f"{vertical}-{week_of}"
    payload = {**data, "vertical": vertical, "weekOf": week_of, "generatedAt": now, "expiresAt": now + timedelta(days=7), "version": "1.0"}
    await asyncio.to_thread(db.collection(COLLECTION).document(doc_id).set, payload)
    logger.info(f"[AiToolsDigest] Saved {doc_id}")
    return doc_id


async def get_ai_tools_digest(vertical: str, week_of: str) -> dict[str, Any] | None:
    db = get_db()
    doc = await asyncio.to_thread(db.collection(COLLECTION).document(f"{vertical}-{week_of}").get)
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    return data


async def get_latest_ai_tools_digest(vertical: str) -> dict[str, Any] | None:
    now = datetime.utcnow()
    for delta in [0, 7]:
        d = now - timedelta(days=delta)
        wk = f"{d.year}-W{d.isocalendar()[1]:02d}"
        result = await get_ai_tools_digest(vertical, wk)
        if result:
            return result
    return None
