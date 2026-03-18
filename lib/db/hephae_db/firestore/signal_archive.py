"""Firestore persistence for pulse_signal_archive collection.

Stores raw API responses per source per zip per week. Enables retroactive
recomputation, weight tuning, new signal backfill, and A/B testing prompts.

Document ID pattern: {zip_code}-{weekOf}
  e.g., "07110-2026-W12"
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

ARCHIVE_COLLECTION = "pulse_signal_archive"


async def save_signal_archive(
    zip_code: str,
    week_of: str,
    sources: dict[str, Any],
    pre_computed_impact: dict[str, Any] | None = None,
) -> str:
    """Save raw signal data for a zip code's weekly pulse.

    Args:
        zip_code: 5-digit zip code.
        week_of: ISO week string (e.g., "2026-W12" or "2026-03-18").
        sources: Dict of source_name → {raw, fetchedAt, version}.
        pre_computed_impact: Optional pre-computed impact multipliers.

    Returns:
        Document ID.
    """
    db = get_db()
    doc_id = f"{zip_code}-{week_of}"
    now = datetime.utcnow()

    doc_ref = db.collection(ARCHIVE_COLLECTION).document(doc_id)
    data: dict[str, Any] = {
        "zipCode": zip_code,
        "weekOf": week_of,
        "collectedAt": now,
        "sources": sources,
    }
    if pre_computed_impact:
        data["preComputedImpact"] = pre_computed_impact

    await asyncio.to_thread(doc_ref.set, data)
    logger.info(f"[SignalArchive] Saved {doc_id} ({len(sources)} sources)")
    return doc_id


async def get_signal_archive(
    zip_code: str,
    week_of: str,
) -> dict[str, Any] | None:
    """Retrieve archived signals for a specific zip + week."""
    db = get_db()
    doc_id = f"{zip_code}-{week_of}"
    doc = await asyncio.to_thread(
        db.collection(ARCHIVE_COLLECTION).document(doc_id).get
    )
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    return data


async def list_signal_archives(
    zip_code: str,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """List recent signal archives for a zip code (most recent first)."""
    db = get_db()
    query = (
        db.collection(ARCHIVE_COLLECTION)
        .where("zipCode", "==", zip_code)
        .order_by("collectedAt", direction="DESCENDING")
        .limit(limit)
    )
    docs = await asyncio.to_thread(query.get)
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        results.append(data)
    return results
