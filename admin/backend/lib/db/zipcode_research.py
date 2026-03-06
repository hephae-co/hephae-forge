"""Firestore persistence for zipcode_research collection."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from backend.lib.firebase import get_db
from backend.types import ZipCodeResearchDocument, ZipCodeReport, ZipCodeRunSummary

logger = logging.getLogger(__name__)

COLLECTION = "zipcode_research"


def _deserialize(doc_id: str, data: dict[str, Any]) -> ZipCodeResearchDocument:
    data["id"] = doc_id
    for field in ("createdAt", "updatedAt"):
        val = data.get(field)
        if val and hasattr(val, "seconds"):
            data[field] = datetime.utcfromtimestamp(val.seconds + val.nanoseconds / 1e9)
    return ZipCodeResearchDocument.model_validate(data)


async def save_zipcode_run(
    zip_code: str,
    report: dict[str, Any],
    run_id: str | None = None,
) -> str:
    db = get_db()
    now = datetime.utcnow()

    if not run_id:
        ts = now.strftime("%Y%m%d%H%M%S")
        run_id = f"{zip_code}-{ts}"

    doc_ref = db.collection(COLLECTION).document(run_id)
    data = {
        "zipCode": zip_code,
        "report": report,
        "createdAt": now,
        "updatedAt": now,
    }
    await asyncio.to_thread(doc_ref.set, data)
    return run_id


async def get_zipcode_report(zip_code: str) -> ZipCodeResearchDocument | None:
    """Get the latest report for a zip code (backward-compatible)."""
    db = get_db()

    # Try new format: query by zipCode field, ordered by createdAt
    query = (
        db.collection(COLLECTION)
        .where("zipCode", "==", zip_code)
        .order_by("createdAt", direction="DESCENDING")
        .limit(1)
    )
    docs = await asyncio.to_thread(query.get)
    if docs:
        doc = docs[0]
        return _deserialize(doc.id, doc.to_dict())

    # Fallback: old format where doc ID = zipCode
    doc = await asyncio.to_thread(db.collection(COLLECTION).document(zip_code).get)
    if doc.exists:
        return _deserialize(doc.id, doc.to_dict())

    return None


async def get_run(run_id: str) -> ZipCodeResearchDocument | None:
    db = get_db()
    doc = await asyncio.to_thread(db.collection(COLLECTION).document(run_id).get)
    if not doc.exists:
        return None
    return _deserialize(doc.id, doc.to_dict())


async def delete_run(run_id: str) -> None:
    db = get_db()
    await asyncio.to_thread(db.collection(COLLECTION).document(run_id).delete)


async def list_zipcode_runs(limit: int = 10) -> list[ZipCodeRunSummary]:
    db = get_db()
    query = db.collection(COLLECTION).order_by("createdAt", direction="DESCENDING").limit(limit)
    docs = await asyncio.to_thread(query.get)

    summaries = []
    for doc in docs:
        data = doc.to_dict()
        report = data.get("report", {})
        sections = report.get("sections", {})
        section_count = sum(1 for v in sections.values() if v)

        created_at = data.get("createdAt")
        if hasattr(created_at, "seconds"):
            created_at = datetime.utcfromtimestamp(created_at.seconds + created_at.nanoseconds / 1e9)

        summaries.append(ZipCodeRunSummary(
            id=doc.id,
            zipCode=data.get("zipCode", ""),
            sectionCount=section_count,
            summarySnippet=(report.get("summary", "") or "")[:200],
            createdAt=created_at or datetime.utcnow(),
        ))
    return summaries


async def get_multiple_runs(run_ids: list[str]) -> list[ZipCodeResearchDocument]:
    results = []
    for run_id in run_ids:
        doc = await get_run(run_id)
        if doc:
            results.append(doc)
    return results
