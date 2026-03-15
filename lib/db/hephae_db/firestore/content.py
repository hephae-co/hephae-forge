"""Firestore persistence for content_posts collection."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "content_posts"


def _deserialize_ts(data: dict[str, Any]) -> None:
    for field in ("createdAt", "updatedAt", "publishedAt"):
        val = data.get(field)
        if val and hasattr(val, "seconds"):
            data[field] = datetime.utcfromtimestamp(val.seconds + val.nanoseconds / 1e9)


async def save_content_post(post: dict[str, Any]) -> str:
    db = get_db()
    doc_ref = db.collection(COLLECTION).document()
    now = datetime.utcnow()
    post["id"] = doc_ref.id
    post["createdAt"] = now
    post["updatedAt"] = now
    await asyncio.to_thread(doc_ref.set, {k: v for k, v in post.items() if v is not None})
    return doc_ref.id


async def get_content_post(post_id: str) -> dict[str, Any] | None:
    db = get_db()
    doc = await asyncio.to_thread(db.collection(COLLECTION).document(post_id).get)
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    _deserialize_ts(data)
    return data


async def list_content_posts(
    limit: int = 20,
    platform: str | None = None,
) -> list[dict[str, Any]]:
    db = get_db()
    query = db.collection(COLLECTION)
    if platform:
        query = query.where("platform", "==", platform)
    query = query.order_by("createdAt", direction="DESCENDING").limit(limit)
    docs = await asyncio.to_thread(query.get)
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        _deserialize_ts(data)
        results.append(data)
    return results


async def update_content_post(post_id: str, updates: dict[str, Any]) -> None:
    db = get_db()
    updates["updatedAt"] = datetime.utcnow()
    await asyncio.to_thread(db.collection(COLLECTION).document(post_id).update, updates)


async def delete_content_post(post_id: str) -> None:
    db = get_db()
    await asyncio.to_thread(db.collection(COLLECTION).document(post_id).delete)
