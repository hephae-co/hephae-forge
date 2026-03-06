"""Firestore persistence for sector_research collection."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import Any

from backend.lib.firebase import get_db
from backend.types import SectorResearchDocument, SectorResearchPhase

logger = logging.getLogger(__name__)

COLLECTION = "sector_research"


def generate_sector_id(sector: str, area_name: str | None = None) -> str:
    """Generate a slug-based ID for a sector."""
    base = f"{sector}-{area_name}" if area_name else sector
    return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")


def _deserialize(doc_id: str, data: dict[str, Any]) -> SectorResearchDocument:
    data["id"] = doc_id
    for field in ("createdAt", "updatedAt"):
        val = data.get(field)
        if val and hasattr(val, "seconds"):
            data[field] = datetime.utcfromtimestamp(val.seconds + val.nanoseconds / 1e9)
    return SectorResearchDocument.model_validate(data)


async def create_sector_research(
    sector: str,
    zip_codes: list[str],
    area_name: str | None = None,
) -> SectorResearchDocument:
    db = get_db()
    sector_id = generate_sector_id(sector, area_name)
    doc_ref = db.collection(COLLECTION).document(sector_id)
    now = datetime.utcnow()

    doc = SectorResearchDocument(
        id=sector_id,
        sector=sector,
        zipCodes=zip_codes,
        areaName=area_name,
        phase=SectorResearchPhase.ANALYZING,
        createdAt=now,
        updatedAt=now,
    )

    await asyncio.to_thread(doc_ref.set, doc.model_dump(mode="json", exclude_none=True))
    return doc


async def save_sector_research(doc: SectorResearchDocument) -> None:
    db = get_db()
    doc.updatedAt = datetime.utcnow()
    await asyncio.to_thread(
        db.collection(COLLECTION).document(doc.id).set,
        doc.model_dump(mode="json", exclude_none=True),
    )


async def load_sector_research(sector_id: str) -> SectorResearchDocument | None:
    db = get_db()
    snapshot = await asyncio.to_thread(db.collection(COLLECTION).document(sector_id).get)
    if not snapshot.exists:
        return None
    return _deserialize(snapshot.id, snapshot.to_dict())


async def list_sector_research(limit: int = 20) -> list[SectorResearchDocument]:
    db = get_db()
    query = db.collection(COLLECTION).order_by("createdAt", direction="DESCENDING").limit(limit)
    docs = await asyncio.to_thread(query.get)
    return [_deserialize(doc.id, doc.to_dict()) for doc in docs]


async def get_sector_research_for_type(sector: str) -> SectorResearchDocument | None:
    """Find sector research by sector name."""
    db = get_db()
    query = (
        db.collection(COLLECTION)
        .where("sector", "==", sector)
        .where("phase", "==", "completed")
        .order_by("createdAt", direction="DESCENDING")
        .limit(1)
    )
    docs = await asyncio.to_thread(query.get)
    if docs:
        return _deserialize(docs[0].id, docs[0].to_dict())
    return None
