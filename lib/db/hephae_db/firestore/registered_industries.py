"""Firestore CRUD for registered industries (global industry onboarding)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "registered_industries"


async def register_industry(
    industry_key: str,
    display_name: str,
    created_by: str = "admin",
) -> dict[str, Any]:
    """Register an industry for weekly national pulse generation."""
    db = get_db()
    now = datetime.utcnow()
    data = {
        "industryKey": industry_key,
        "displayName": display_name,
        "status": "active",
        "registeredAt": now,
        "lastPulseAt": None,
        "lastPulseId": None,
        "pulseCount": 0,
        "createdBy": created_by,
    }
    await asyncio.to_thread(db.collection(COLLECTION).document(industry_key).set, data)
    logger.info(f"[RegisteredIndustries] Registered {industry_key} ({display_name})")
    return {**data, "id": industry_key}


async def unregister_industry(industry_key: str) -> None:
    """Remove an industry registration."""
    db = get_db()
    await asyncio.to_thread(db.collection(COLLECTION).document(industry_key).delete)
    logger.info(f"[RegisteredIndustries] Unregistered {industry_key}")


async def get_registered_industry(industry_key: str) -> dict[str, Any] | None:
    """Get a single registered industry."""
    db = get_db()
    snapshot = await asyncio.to_thread(db.collection(COLLECTION).document(industry_key).get)
    if not snapshot.exists:
        return None
    data = snapshot.to_dict()
    data["id"] = snapshot.id
    return data


async def list_registered_industries(status: str | None = None) -> list[dict[str, Any]]:
    """List all registered industries, optionally filtered by status."""
    db = get_db()
    query = db.collection(COLLECTION).order_by("registeredAt", direction="DESCENDING")
    if status:
        query = (
            db.collection(COLLECTION)
            .where("status", "==", status)
            .order_by("registeredAt", direction="DESCENDING")
        )
    docs = await asyncio.to_thread(query.get)
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        results.append(data)
    return results


async def update_last_industry_pulse(
    industry_key: str, pulse_id: str
) -> None:
    """Update tracking fields after successful industry pulse."""
    db = get_db()
    from google.cloud.firestore_v1 import Increment
    await asyncio.to_thread(
        db.collection(COLLECTION).document(industry_key).update,
        {
            "lastPulseAt": datetime.utcnow(),
            "lastPulseId": pulse_id,
            "pulseCount": Increment(1),
        },
    )


async def pause_industry(industry_key: str) -> None:
    """Pause an industry (skip in cron)."""
    db = get_db()
    await asyncio.to_thread(
        db.collection(COLLECTION).document(industry_key).update,
        {"status": "paused"},
    )


async def resume_industry(industry_key: str) -> None:
    """Resume a paused industry."""
    db = get_db()
    await asyncio.to_thread(
        db.collection(COLLECTION).document(industry_key).update,
        {"status": "active"},
    )
