"""Firestore persistence for content_posts collection."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from backend.lib.firebase import get_db
from backend.types import ContentPost

logger = logging.getLogger(__name__)

COLLECTION = "content_posts"


def _deserialize(doc_id: str, data: dict[str, Any]) -> ContentPost:
    data["id"] = doc_id
    for field in ("createdAt", "updatedAt", "publishedAt"):
        val = data.get(field)
        if val and hasattr(val, "seconds"):
            data[field] = datetime.utcfromtimestamp(val.seconds + val.nanoseconds / 1e9)
    return ContentPost.model_validate(data)


async def save_content_post(post: ContentPost) -> str:
    db = get_db()
    doc_ref = db.collection(COLLECTION).document()
    now = datetime.utcnow()
    post.id = doc_ref.id
    post.createdAt = now
    post.updatedAt = now
    await asyncio.to_thread(doc_ref.set, post.model_dump(mode="json", exclude_none=True))
    return doc_ref.id


async def get_content_post(post_id: str) -> ContentPost | None:
    db = get_db()
    doc = await asyncio.to_thread(db.collection(COLLECTION).document(post_id).get)
    if not doc.exists:
        return None
    return _deserialize(doc.id, doc.to_dict())


async def list_content_posts(
    limit: int = 20,
    platform: str | None = None,
) -> list[ContentPost]:
    db = get_db()
    query = db.collection(COLLECTION)
    if platform:
        query = query.where("platform", "==", platform)
    query = query.order_by("createdAt", direction="DESCENDING").limit(limit)
    docs = await asyncio.to_thread(query.get)
    return [_deserialize(doc.id, doc.to_dict()) for doc in docs]


async def update_content_post(post_id: str, updates: dict[str, Any]) -> None:
    db = get_db()
    updates["updatedAt"] = datetime.utcnow()
    await asyncio.to_thread(db.collection(COLLECTION).document(post_id).update, updates)


async def delete_content_post(post_id: str) -> None:
    db = get_db()
    await asyncio.to_thread(db.collection(COLLECTION).document(post_id).delete)
