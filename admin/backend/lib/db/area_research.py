"""Firestore persistence for area_research collection."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import Any

from backend.lib.firebase import get_db
from backend.types import AreaResearchDocument, AreaResearchPhase

logger = logging.getLogger(__name__)

COLLECTION = "area_research"


def generate_area_key(area: str, business_type: str) -> str:
    """Generate a slug-based key for area + business type."""
    combined = f"{area}-{business_type}".lower()
    slug = re.sub(r"[^a-z0-9]+", "-", combined).strip("-")
    return slug


def _deserialize(doc_id: str, data: dict[str, Any]) -> AreaResearchDocument:
    data["id"] = doc_id
    for field in ("createdAt", "updatedAt"):
        val = data.get(field)
        if val and hasattr(val, "seconds"):
            data[field] = datetime.utcfromtimestamp(val.seconds + val.nanoseconds / 1e9)
    return AreaResearchDocument.model_validate(data)


async def create_area_research(
    area: str,
    business_type: str,
    zip_codes: list[str],
    county_name: str | None = None,
    state: str | None = None,
) -> AreaResearchDocument:
    db = get_db()
    doc_ref = db.collection(COLLECTION).document()
    now = datetime.utcnow()
    area_key = generate_area_key(area, business_type)

    doc = AreaResearchDocument(
        id=doc_ref.id,
        area=area,
        businessType=business_type,
        areaKey=area_key,
        resolvedCountyName=county_name,
        resolvedState=state,
        zipCodes=zip_codes,
        completedZipCodes=[],
        failedZipCodes=[],
        phase=AreaResearchPhase.RESOLVING,
        createdAt=now,
        updatedAt=now,
    )

    await asyncio.to_thread(doc_ref.set, doc.model_dump(mode="json", exclude_none=True))
    return doc


async def save_area_research(doc: AreaResearchDocument) -> None:
    db = get_db()
    doc.updatedAt = datetime.utcnow()
    await asyncio.to_thread(
        db.collection(COLLECTION).document(doc.id).set,
        doc.model_dump(mode="json", exclude_none=True),
    )


async def load_area_research(area_id: str) -> AreaResearchDocument | None:
    db = get_db()
    snapshot = await asyncio.to_thread(db.collection(COLLECTION).document(area_id).get)
    if not snapshot.exists:
        return None
    return _deserialize(snapshot.id, snapshot.to_dict())


async def list_area_research(limit: int = 20) -> list[AreaResearchDocument]:
    db = get_db()
    query = db.collection(COLLECTION).order_by("createdAt", direction="DESCENDING").limit(limit)
    docs = await asyncio.to_thread(query.get)
    return [_deserialize(doc.id, doc.to_dict()) for doc in docs]


async def delete_area_research(area_id: str) -> None:
    db = get_db()
    await asyncio.to_thread(db.collection(COLLECTION).document(area_id).delete)


async def get_area_research_for_zip_code(zip_code: str) -> AreaResearchDocument | None:
    """Find area research that includes a specific zip code."""
    db = get_db()
    query = (
        db.collection(COLLECTION)
        .where("zipCodes", "array_contains", zip_code)
        .where("phase", "==", "completed")
        .order_by("createdAt", direction="DESCENDING")
        .limit(1)
    )
    docs = await asyncio.to_thread(query.get)
    if docs:
        return _deserialize(docs[0].id, docs[0].to_dict())
    return None
