"""Firestore CRUD for industry-level weekly pulse (national signals)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "industry_pulses"


async def save_industry_pulse(
    industry_key: str,
    week_of: str,
    national_signals: dict[str, Any],
    national_impact: dict[str, Any],
    national_playbooks: list[dict],
    trend_summary: str,
    signals_used: list[str],
    diagnostics: dict[str, Any] | None = None,
) -> str:
    """Save an industry pulse. Doc ID: {industry_key}-{weekOf}."""
    db = get_db()
    doc_id = f"{industry_key}-{week_of}"
    now = datetime.utcnow()

    data = {
        "industryKey": industry_key,
        "weekOf": week_of,
        "nationalSignals": national_signals,
        "nationalImpact": national_impact,
        "nationalPlaybooks": national_playbooks,
        "trendSummary": trend_summary,
        "signalsUsed": signals_used,
        "diagnostics": diagnostics or {},
        "createdAt": now,
        "updatedAt": now,
    }

    await asyncio.to_thread(
        db.collection(COLLECTION).document(doc_id).set, data
    )
    logger.info(f"[IndustryPulse] Saved {doc_id}")
    return doc_id


async def get_industry_pulse(
    industry_key: str,
    week_of: str,
) -> dict[str, Any] | None:
    """Get industry pulse for a given week."""
    db = get_db()
    doc_id = f"{industry_key}-{week_of}"
    snapshot = await asyncio.to_thread(
        db.collection(COLLECTION).document(doc_id).get
    )
    if not snapshot.exists:
        return None
    data = snapshot.to_dict()
    data["id"] = snapshot.id
    return data


async def get_latest_industry_pulse(
    industry_key: str,
) -> dict[str, Any] | None:
    """Get the most recent industry pulse."""
    db = get_db()
    query = (
        db.collection(COLLECTION)
        .where("industryKey", "==", industry_key)
        .order_by("createdAt", direction="DESCENDING")
        .limit(1)
    )
    docs = await asyncio.to_thread(query.get)
    if docs:
        data = docs[0].to_dict()
        data["id"] = docs[0].id
        return data
    return None


async def list_industry_pulses(
    industry_key: str | None = None,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """List recent industry pulses."""
    db = get_db()
    query = db.collection(COLLECTION).order_by("createdAt", direction="DESCENDING").limit(limit)
    if industry_key:
        query = (
            db.collection(COLLECTION)
            .where("industryKey", "==", industry_key)
            .order_by("createdAt", direction="DESCENDING")
            .limit(limit)
        )
    docs = await asyncio.to_thread(query.get)
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        results.append(data)
    return results
