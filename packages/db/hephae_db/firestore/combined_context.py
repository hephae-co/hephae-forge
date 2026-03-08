"""Firestore persistence for combined_contexts collection."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "combined_contexts"


def _deserialize_ts(data: dict[str, Any]) -> None:
    val = data.get("createdAt")
    if val and hasattr(val, "seconds"):
        data["createdAt"] = datetime.utcfromtimestamp(val.seconds + val.nanoseconds / 1e9)


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


async def get_combined_context(context_id: str) -> dict[str, Any] | None:
    db = get_db()
    doc = await asyncio.to_thread(db.collection(COLLECTION).document(context_id).get)
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    _deserialize_ts(data)
    return data


async def list_combined_contexts(limit: int = 10) -> list[dict[str, Any]]:
    db = get_db()
    query = db.collection(COLLECTION).order_by("createdAt", direction="DESCENDING").limit(limit)
    docs = await asyncio.to_thread(query.get)
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        _deserialize_ts(data)
        results.append(data)
    return results


async def delete_combined_context(context_id: str) -> None:
    db = get_db()
    await asyncio.to_thread(db.collection(COLLECTION).document(context_id).delete)
