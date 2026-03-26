"""Firestore persistence for ai_tool_discovery_runs collection.

Stores weekly AI tool discovery results per industry vertical.
Document ID: {vertical}-{weekOf} (e.g., restaurant-2026-W12)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "ai_tool_discovery_runs"


def _deserialize_ts(data: dict[str, Any]) -> dict[str, Any]:
    """Convert Firestore timestamps to ISO strings in-place."""
    for field in ("generatedAt", "createdAt", "expireAt"):
        val = data.get(field)
        if val is None:
            continue
        if hasattr(val, "seconds"):
            data[field] = datetime.utcfromtimestamp(
                val.seconds + val.nanoseconds / 1e9
            ).isoformat()
        elif hasattr(val, "isoformat"):
            data[field] = val.isoformat()
    return data


async def save_ai_tool_run(
    vertical: str,
    week_of: str,
    tools: list[dict[str, Any]],
    weekly_highlight: dict[str, str],
    test_mode: bool = False,
    expire_at: datetime | None = None,
) -> str:
    """Save a discovery run. Returns the document ID."""
    db = get_db()
    doc_id = f"{vertical}-{week_of}"
    doc_ref = db.collection(COLLECTION).document(doc_id)
    now = datetime.utcnow()

    new_tools = [t for t in tools if t.get("isNew")]
    high_rel = [t for t in tools if t.get("relevanceScore") == "HIGH"]

    data: dict[str, Any] = {
        "vertical": vertical,
        "weekOf": week_of,
        "tools": tools,
        "weeklyHighlight": weekly_highlight,
        "totalToolsFound": len(tools),
        "newToolsCount": len(new_tools),
        "highRelevanceCount": len(high_rel),
        "generatedAt": now,
        "createdAt": now,
    }
    if test_mode:
        data["testMode"] = True
    if expire_at:
        data["expireAt"] = expire_at

    await asyncio.to_thread(doc_ref.set, data)
    logger.info(f"[AiToolDiscovery] Saved {doc_id} ({len(tools)} tools)")
    return doc_id


async def get_ai_tool_run(vertical: str, week_of: str) -> dict[str, Any] | None:
    """Get a specific run by vertical + week."""
    db = get_db()
    doc_id = f"{vertical}-{week_of}"
    doc = await asyncio.to_thread(db.collection(COLLECTION).document(doc_id).get)
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    return _deserialize_ts(data)


async def get_latest_ai_tool_run(vertical: str) -> dict[str, Any] | None:
    """Get the most recent run for a vertical."""
    runs = await list_ai_tool_runs(vertical=vertical, limit=1, summaries_only=False)
    return runs[0] if runs else None


async def list_ai_tool_runs(
    vertical: str | None = None,
    limit: int = 20,
    summaries_only: bool = True,
) -> list[dict[str, Any]]:
    """List recent discovery runs, optionally filtered by vertical.

    Uses simple equality filter (no composite index needed).
    Sorts in Python, same pattern as list_tech_intelligence.
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
        _deserialize_ts(data)
        if summaries_only:
            results.append({
                "id": doc.id,
                "vertical": data.get("vertical", ""),
                "weekOf": data.get("weekOf", ""),
                "totalToolsFound": data.get("totalToolsFound", 0),
                "newToolsCount": data.get("newToolsCount", 0),
                "highRelevanceCount": data.get("highRelevanceCount", 0),
                "weeklyHighlight": data.get("weeklyHighlight", {}),
                "generatedAt": data.get("generatedAt"),
                "testMode": data.get("testMode", False),
            })
        else:
            results.append(data)

    results.sort(key=lambda x: str(x.get("generatedAt", "")), reverse=True)
    return results[:limit]


async def delete_ai_tool_run(doc_id: str) -> None:
    """Delete a run by document ID."""
    db = get_db()
    await asyncio.to_thread(db.collection(COLLECTION).document(doc_id).delete)
    logger.info(f"[AiToolDiscovery] Deleted {doc_id}")
