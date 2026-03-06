"""Firestore operations for the businesses collection."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from backend.lib.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "businesses"


async def get_businesses_in_zipcode(zip_code: str, limit: int = 20) -> list[dict[str, Any]]:
    db = get_db()
    query = db.collection(COLLECTION).where("zipCode", "==", zip_code).limit(limit)
    docs = await asyncio.to_thread(query.get)
    return [{"docId": doc.id, **doc.to_dict()} for doc in docs]


async def save_business(slug: str, data: dict[str, Any]) -> None:
    db = get_db()
    data["updatedAt"] = datetime.utcnow()
    if "createdAt" not in data:
        data["createdAt"] = datetime.utcnow()
    await asyncio.to_thread(db.collection(COLLECTION).document(slug).set, data, True)  # merge=True


async def get_business(doc_id: str) -> dict[str, Any] | None:
    db = get_db()
    doc = await asyncio.to_thread(db.collection(COLLECTION).document(doc_id).get)
    if not doc.exists:
        return None
    return {"docId": doc.id, **doc.to_dict()}


async def update_latest_outputs(doc_id: str, latest_outputs: dict[str, Any]) -> None:
    db = get_db()
    from google.cloud.firestore import SERVER_TIMESTAMP
    await asyncio.to_thread(
        db.collection(COLLECTION).document(doc_id).update,
        {"latestOutputs": latest_outputs, "updatedAt": SERVER_TIMESTAMP},
    )


async def delete_business(doc_id: str) -> None:
    db = get_db()
    await asyncio.to_thread(db.collection(COLLECTION).document(doc_id).delete)
