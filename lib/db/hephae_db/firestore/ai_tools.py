"""Firestore serving layer for ai_tools collection.

Collection: ai_tools/{tool_id}

One document per canonical tool. Verticals appear as a nested map so the
same tool record is never duplicated across verticals. BQ (hephae.ai_tools)
holds the full append-only history for analytics; this collection is the
fast serving layer for the chat UI, blog writer, and any interactive surface.

Document shape:
  toolId              string     — stable 12-char SHA-1 ID
  toolName            string
  vendor              string
  technologyCategory  string     — "Gemini AI Studio", "GPT Store", "Standalone SaaS", etc.
  url                 string
  description         string
  pricing             string
  isFree              bool
  freeAlternativeTo   string | null
  aiCapability        string
  reputationTier      string     — ESTABLISHED | GROWING | NEW
  sourceUrl           string
  firstSeenWeek       string     — ISO week of first discovery (e.g., "2026-W13")
  firstSeenAt         timestamp
  weeksSeen           int        — incremented each week the tool appears in any run
  lastUpdatedAt       timestamp
  verticalsList       string[]   — flat array of vertical keys (e.g., ["restaurant", "bakery"])
                                   used for array_contains queries (no composite index needed)
  verticals           map        — one entry per vertical:
    {vertical}: {
      relevanceScore   string    — HIGH | MEDIUM | LOW
      category         string
      actionForOwner   string
      assessedWeek     string
      assessedAt       timestamp
    }
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from google.cloud import firestore

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "ai_tools"


async def upsert_tool(
    *,
    tool_id: str,
    tool: dict[str, Any],
    vertical: str,
    week_of: str,
    is_new: bool,
) -> None:
    """Upsert a canonical tool document. Fire-and-forget — failures logged only.

    On first appearance (is_new=True): sets firstSeenWeek + firstSeenAt.
    Every call: increments weeksSeen, updates vertical-specific data.
    Uses update() with dotted paths to safely merge verticals without overwriting
    other vertical entries.
    """
    db = get_db()
    ref = db.collection(COLLECTION).document(tool_id)
    now = datetime.utcnow()

    top_level: dict[str, Any] = {
        "toolId": tool_id,
        "toolName": tool.get("toolName", ""),
        "vendor": tool.get("vendor", ""),
        "technologyCategory": tool.get("technologyCategory", "Standalone SaaS"),
        "url": tool.get("url") or "",
        "description": tool.get("description") or "",
        "pricing": tool.get("pricing") or "",
        "isFree": bool(tool.get("isFree", False)),
        "freeAlternativeTo": tool.get("freeAlternativeTo"),
        "aiCapability": tool.get("aiCapability") or "",
        "reputationTier": tool.get("reputationTier") or "",
        "sourceUrl": tool.get("sourceUrl") or "",
        "weeksSeen": firestore.Increment(1),
        "lastUpdatedAt": now,
    }
    if is_new:
        top_level["firstSeenWeek"] = week_of
        top_level["firstSeenAt"] = now

    vertical_data: dict[str, Any] = {
        "relevanceScore": tool.get("relevanceScore", "MEDIUM"),
        "category": tool.get("category") or "",
        "actionForOwner": tool.get("actionForOwner") or "",
        "assessedWeek": week_of,
        "assessedAt": now,
    }

    def _write() -> None:
        try:
            # update() supports dotted-path merging and Increment transforms.
            # verticalsList uses ArrayUnion so the vertical is added only once.
            ref.update({
                **top_level,
                f"verticals.{vertical}": vertical_data,
                "verticalsList": firestore.ArrayUnion([vertical]),
            })
        except Exception:
            # Doc doesn't exist yet — create it with set()
            ref.set({
                **{k: (1 if k == "weeksSeen" else v) for k, v in top_level.items()},
                "firstSeenWeek": week_of,
                "firstSeenAt": now,
                "verticals": {vertical: vertical_data},
                "verticalsList": [vertical],
            })

    try:
        await asyncio.to_thread(_write)
    except Exception as e:
        logger.warning(f"[AiTools] Firestore upsert failed for {tool_id}: {e}")


async def get_tools_for_vertical(
    vertical: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Get tools that have appeared for a vertical, ordered by weeksSeen descending.

    Used by the chat UI and blog writer to surface relevant AI tools for a
    given business type.
    """
    db = get_db()

    def _query() -> list[dict[str, Any]]:
        # Filter by verticalsList array (single-field auto-index, no composite needed).
        # Sort by weeksSeen in Python — avoids composite index per vertical.
        docs = (
            db.collection(COLLECTION)
            .where("verticalsList", "array_contains", vertical)
            .limit(limit * 3)  # fetch extra to allow Python-side sorting
            .get()
        )
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            _deserialize_ts(data)
            results.append(data)
        results.sort(key=lambda d: d.get("weeksSeen", 0), reverse=True)
        return results[:limit]

    try:
        return await asyncio.to_thread(_query)
    except Exception as e:
        logger.warning(f"[AiTools] get_tools_for_vertical failed ({vertical}): {e}")
        return []


async def get_tool(tool_id: str) -> dict[str, Any] | None:
    """Fetch a single tool by its stable ID."""
    db = get_db()

    def _get() -> dict[str, Any] | None:
        doc = db.collection(COLLECTION).document(tool_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        data["id"] = doc.id
        _deserialize_ts(data)
        return data

    try:
        return await asyncio.to_thread(_get)
    except Exception as e:
        logger.warning(f"[AiTools] get_tool failed ({tool_id}): {e}")
        return None


async def get_top_tools(
    limit: int = 10,
    technology_category: str | None = None,
    is_free: bool | None = None,
) -> list[dict[str, Any]]:
    """Get globally popular tools across all verticals.

    Used for the monthly digest and cross-vertical AI tool insights.
    """
    db = get_db()

    def _query() -> list[dict[str, Any]]:
        q = db.collection(COLLECTION).order_by(
            "weeksSeen", direction=firestore.Query.DESCENDING
        )
        if technology_category:
            q = q.where("technologyCategory", "==", technology_category)
        if is_free is not None:
            q = q.where("isFree", "==", is_free)
        docs = q.limit(limit).get()
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            _deserialize_ts(data)
            results.append(data)
        return results

    try:
        return await asyncio.to_thread(_query)
    except Exception as e:
        logger.warning(f"[AiTools] get_top_tools failed: {e}")
        return []


def _deserialize_ts(data: dict[str, Any]) -> None:
    """In-place convert Firestore timestamps to ISO strings."""
    for key in ("firstSeenAt", "lastUpdatedAt"):
        val = data.get(key)
        if val and hasattr(val, "seconds"):
            data[key] = datetime.utcfromtimestamp(
                val.seconds + val.nanoseconds / 1e9
            ).isoformat()
        elif hasattr(val, "isoformat"):
            data[key] = val.isoformat()
    # Also deserialize inside verticals map
    for v_data in (data.get("verticals") or {}).values():
        if isinstance(v_data, dict):
            ts = v_data.get("assessedAt")
            if ts and hasattr(ts, "seconds"):
                v_data["assessedAt"] = datetime.utcfromtimestamp(
                    ts.seconds + ts.nanoseconds / 1e9
                ).isoformat()
