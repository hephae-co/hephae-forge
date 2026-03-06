"""Firestore persistence for combined_contexts collection."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from backend.lib.firebase import get_db
from backend.types import CombinedContext, CombinedContextData

logger = logging.getLogger(__name__)

COLLECTION = "combined_contexts"


def _deserialize(doc_id: str, data: dict[str, Any]) -> CombinedContext:
    data["id"] = doc_id
    val = data.get("createdAt")
    if val and hasattr(val, "seconds"):
        data["createdAt"] = datetime.utcfromtimestamp(val.seconds + val.nanoseconds / 1e9)
    return CombinedContext.model_validate(data)


async def save_combined_context(
    source_run_ids: list[str],
    source_zip_codes: list[str],
    context: dict[str, Any],
) -> str:
    db = get_db()
    doc_ref = db.collection(COLLECTION).document()
    now = datetime.utcnow()

    data = {
        "sourceRunIds": source_run_ids,
        "sourceZipCodes": source_zip_codes,
        "context": context,
        "createdAt": now,
    }
    await asyncio.to_thread(doc_ref.set, data)
    return doc_ref.id


async def get_combined_context(context_id: str) -> CombinedContext | None:
    db = get_db()
    doc = await asyncio.to_thread(db.collection(COLLECTION).document(context_id).get)
    if not doc.exists:
        return None
    return _deserialize(doc.id, doc.to_dict())


async def list_combined_contexts(limit: int = 10) -> list[CombinedContext]:
    db = get_db()
    query = db.collection(COLLECTION).order_by("createdAt", direction="DESCENDING").limit(limit)
    docs = await asyncio.to_thread(query.get)
    return [_deserialize(doc.id, doc.to_dict()) for doc in docs]


async def delete_combined_context(context_id: str) -> None:
    db = get_db()
    await asyncio.to_thread(db.collection(COLLECTION).document(context_id).delete)
