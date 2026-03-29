"""Firestore CRUD for user_feedback collection.

Collection: user_feedback/{auto-id}

One document per vote. Each thumbs-up or thumbs-down on any data element
(pulse insight, margin item, competitor card, etc.) produces one document.
Queried by admin for aggregate quality scoring per data type / vertical.

Document shape:
  userId          string | null   — Firebase UID (null for guests)
  sessionId       string          — uuid from browser sessionStorage
  businessSlug    string
  zipCode         string | null   — first-class field per DB conventions
  vertical        string | null   — e.g. "restaurant", "bakery"
  dataType        string          — FeedbackDataType enum key
  itemId          string          — stable identifier for the data item
  itemLabel       string          — first 60 chars of item text (admin display)
  rating          "up" | "down"
  tags            string[]        — selected tags (empty for thumbs-up)
  comment         string | null   — optional free text, max 140 chars
  createdAt       timestamp       — SERVER_TIMESTAMP
  appVersion      string          — e.g. "1.0" (for future schema migration)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from google.cloud.firestore import SERVER_TIMESTAMP

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "user_feedback"
APP_VERSION = "1.0"


async def write_feedback(
    *,
    session_id: str,
    business_slug: str,
    data_type: str,
    item_id: str,
    item_label: str,
    rating: str,
    zip_code: str | None = None,
    vertical: str | None = None,
    user_id: str | None = None,
    tags: list[str] | None = None,
    comment: str | None = None,
) -> str:
    """Write a single feedback vote. Returns the new document ID."""
    db = get_db()
    doc: dict[str, Any] = {
        "userId": user_id,
        "sessionId": session_id,
        "businessSlug": business_slug,
        "zipCode": zip_code,
        "vertical": vertical,
        "dataType": data_type,
        "itemId": item_id,
        "itemLabel": item_label[:60],
        "rating": rating,
        "tags": tags or [],
        "comment": comment[:140] if comment else None,
        "createdAt": SERVER_TIMESTAMP,
        "appVersion": APP_VERSION,
    }

    def _write() -> str:
        ref = db.collection(COLLECTION).document()
        ref.set(doc)
        return ref.id

    try:
        doc_id = await asyncio.to_thread(_write)
        logger.info(f"[Feedback] {rating} on {data_type}/{item_id} for {business_slug}")
        return doc_id
    except Exception as e:
        logger.warning(f"[Feedback] Write failed: {e}")
        raise


async def get_feedback_summary(
    *,
    data_type: str | None = None,
    vertical: str | None = None,
    business_slug: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Return aggregate summary + raw items for admin dashboard.

    Summary: upCount, downCount, topTags (sorted by frequency).
    Items: most recent `limit` raw feedback docs.
    """
    db = get_db()

    def _query() -> list[dict[str, Any]]:
        q = db.collection(COLLECTION)
        if data_type:
            q = q.where("dataType", "==", data_type)
        if vertical:
            q = q.where("vertical", "==", vertical)
        if business_slug:
            q = q.where("businessSlug", "==", business_slug)
        q = q.order_by("createdAt", direction="DESCENDING")
        # Fetch offset+limit to support pagination
        docs = q.limit(offset + limit).get()
        return [{"id": d.id, **d.to_dict()} for d in docs]

    try:
        rows = await asyncio.to_thread(_query)
    except Exception as e:
        logger.warning(f"[Feedback] Query failed: {e}")
        rows = []

    # Paginate
    items = rows[offset:]

    # Aggregate
    up_count = sum(1 for r in rows if r.get("rating") == "up")
    down_count = sum(1 for r in rows if r.get("rating") == "down")

    tag_counts: dict[str, int] = {}
    for r in rows:
        for tag in r.get("tags") or []:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    top_tags = sorted(
        [{"tag": t, "count": c} for t, c in tag_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )

    # Serialize timestamps to ISO strings
    for item in items:
        ts = item.get("createdAt")
        if ts and hasattr(ts, "isoformat"):
            item["createdAt"] = ts.isoformat()
        elif ts and hasattr(ts, "seconds"):
            from datetime import datetime
            item["createdAt"] = datetime.utcfromtimestamp(
                ts.seconds + ts.nanoseconds / 1e9
            ).isoformat()

    return {
        "summary": {
            "upCount": up_count,
            "downCount": down_count,
            "totalCount": up_count + down_count,
            "helpfulPct": round(up_count / (up_count + down_count) * 100) if (up_count + down_count) else None,
            "topTags": top_tags[:10],
        },
        "items": items,
    }
