"""Firestore persistence for research collections (zipcode, area, sector).

Merged from admin/backend/lib/db/{zipcode_research,area_research,sector_research}.py.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import Any

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Zipcode Research
# ---------------------------------------------------------------------------

ZIPCODE_COLLECTION = "zipcode_research"


def _deserialize_ts(data: dict[str, Any], fields: list[str]) -> None:
    """In-place convert Firestore timestamps to datetime."""
    for field in fields:
        val = data.get(field)
        if val and hasattr(val, "seconds"):
            data[field] = datetime.utcfromtimestamp(val.seconds + val.nanoseconds / 1e9)


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

    doc_ref = db.collection(ZIPCODE_COLLECTION).document(run_id)
    data = {
        "zipCode": zip_code,
        "report": report,
        "createdAt": now,
        "updatedAt": now,
    }
    await asyncio.to_thread(doc_ref.set, data)
    return run_id


async def get_zipcode_research(zip_code: str) -> dict[str, Any] | None:
    """Get the latest report for a zip code. Returns raw dict."""
    db = get_db()

    query = (
        db.collection(ZIPCODE_COLLECTION)
        .where("zipCode", "==", zip_code)
        .order_by("createdAt", direction="DESCENDING")
        .limit(1)
    )
    docs = await asyncio.to_thread(query.get)
    if docs:
        data = docs[0].to_dict()
        data["id"] = docs[0].id
        _deserialize_ts(data, ["createdAt", "updatedAt"])
        return data

    # Fallback: old format where doc ID = zipCode
    doc = await asyncio.to_thread(db.collection(ZIPCODE_COLLECTION).document(zip_code).get)
    if doc.exists:
        data = doc.to_dict()
        data["id"] = doc.id
        _deserialize_ts(data, ["createdAt", "updatedAt"])
        return data

    return None


async def get_zipcode_run(run_id: str) -> dict[str, Any] | None:
    db = get_db()
    doc = await asyncio.to_thread(db.collection(ZIPCODE_COLLECTION).document(run_id).get)
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    _deserialize_ts(data, ["createdAt", "updatedAt"])
    return data


async def delete_zipcode_run(run_id: str) -> None:
    db = get_db()
    await asyncio.to_thread(db.collection(ZIPCODE_COLLECTION).document(run_id).delete)


async def list_zipcode_runs(limit: int = 10) -> list[dict[str, Any]]:
    db = get_db()
    query = db.collection(ZIPCODE_COLLECTION).order_by("createdAt", direction="DESCENDING").limit(limit)
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

        summaries.append({
            "id": doc.id,
            "zipCode": data.get("zipCode", ""),
            "sectionCount": section_count,
            "summarySnippet": (report.get("summary", "") or "")[:200],
            "createdAt": created_at or datetime.utcnow(),
        })
    return summaries


# ---------------------------------------------------------------------------
# Area Research
# ---------------------------------------------------------------------------

AREA_COLLECTION = "area_research"


def generate_area_key(area: str, business_type: str) -> str:
    combined = f"{area}-{business_type}".lower()
    return re.sub(r"[^a-z0-9]+", "-", combined).strip("-")


async def create_area_research(
    area: str,
    business_type: str,
    zip_codes: list[str],
    county_name: str | None = None,
    state: str | None = None,
) -> dict[str, Any]:
    db = get_db()
    doc_ref = db.collection(AREA_COLLECTION).document()
    now = datetime.utcnow()
    area_key = generate_area_key(area, business_type)

    data = {
        "id": doc_ref.id,
        "area": area,
        "businessType": business_type,
        "areaKey": area_key,
        "resolvedCountyName": county_name,
        "resolvedState": state,
        "zipCodes": zip_codes,
        "completedZipCodes": [],
        "failedZipCodes": [],
        "phase": "resolving",
        "createdAt": now,
        "updatedAt": now,
    }

    await asyncio.to_thread(doc_ref.set, {k: v for k, v in data.items() if v is not None})
    return data


async def save_area_research(doc: dict[str, Any]) -> None:
    db = get_db()
    doc["updatedAt"] = datetime.utcnow()
    doc_id = doc["id"]
    await asyncio.to_thread(
        db.collection(AREA_COLLECTION).document(doc_id).set,
        {k: v for k, v in doc.items() if v is not None},
    )


async def load_area_research(area_id: str) -> dict[str, Any] | None:
    db = get_db()
    snapshot = await asyncio.to_thread(db.collection(AREA_COLLECTION).document(area_id).get)
    if not snapshot.exists:
        return None
    data = snapshot.to_dict()
    data["id"] = snapshot.id
    _deserialize_ts(data, ["createdAt", "updatedAt"])
    return data


async def list_area_research(limit: int = 20) -> list[dict[str, Any]]:
    db = get_db()
    query = db.collection(AREA_COLLECTION).order_by("createdAt", direction="DESCENDING").limit(limit)
    docs = await asyncio.to_thread(query.get)
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        _deserialize_ts(data, ["createdAt", "updatedAt"])
        results.append(data)
    return results


async def delete_area_research(area_id: str) -> None:
    db = get_db()
    await asyncio.to_thread(db.collection(AREA_COLLECTION).document(area_id).delete)


async def get_area_research_for_zip_code(zip_code: str) -> dict[str, Any] | None:
    db = get_db()
    query = (
        db.collection(AREA_COLLECTION)
        .where("zipCodes", "array_contains", zip_code)
        .where("phase", "==", "completed")
        .order_by("createdAt", direction="DESCENDING")
        .limit(1)
    )
    docs = await asyncio.to_thread(query.get)
    if docs:
        data = docs[0].to_dict()
        data["id"] = docs[0].id
        _deserialize_ts(data, ["createdAt", "updatedAt"])
        return data
    return None


# ---------------------------------------------------------------------------
# Sector Research
# ---------------------------------------------------------------------------

SECTOR_COLLECTION = "sector_research"


def generate_sector_id(sector: str, area_name: str | None = None) -> str:
    base = f"{sector}-{area_name}" if area_name else sector
    return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")


async def create_sector_research(
    sector: str,
    zip_codes: list[str],
    area_name: str | None = None,
) -> dict[str, Any]:
    db = get_db()
    sector_id = generate_sector_id(sector, area_name)
    doc_ref = db.collection(SECTOR_COLLECTION).document(sector_id)
    now = datetime.utcnow()

    data = {
        "id": sector_id,
        "sector": sector,
        "zipCodes": zip_codes,
        "areaName": area_name,
        "phase": "analyzing",
        "createdAt": now,
        "updatedAt": now,
    }

    await asyncio.to_thread(doc_ref.set, {k: v for k, v in data.items() if v is not None})
    return data


async def save_sector_research(doc: dict[str, Any]) -> None:
    db = get_db()
    doc["updatedAt"] = datetime.utcnow()
    doc_id = doc["id"]
    await asyncio.to_thread(
        db.collection(SECTOR_COLLECTION).document(doc_id).set,
        {k: v for k, v in doc.items() if v is not None},
    )


async def load_sector_research(sector_id: str) -> dict[str, Any] | None:
    db = get_db()
    snapshot = await asyncio.to_thread(db.collection(SECTOR_COLLECTION).document(sector_id).get)
    if not snapshot.exists:
        return None
    data = snapshot.to_dict()
    data["id"] = snapshot.id
    _deserialize_ts(data, ["createdAt", "updatedAt"])
    return data


async def list_sector_research(limit: int = 20) -> list[dict[str, Any]]:
    db = get_db()
    query = db.collection(SECTOR_COLLECTION).order_by("createdAt", direction="DESCENDING").limit(limit)
    docs = await asyncio.to_thread(query.get)
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        _deserialize_ts(data, ["createdAt", "updatedAt"])
        results.append(data)
    return results


async def get_sector_research_for_type(sector: str) -> dict[str, Any] | None:
    db = get_db()
    query = (
        db.collection(SECTOR_COLLECTION)
        .where("sector", "==", sector)
        .where("phase", "==", "completed")
        .order_by("createdAt", direction="DESCENDING")
        .limit(1)
    )
    docs = await asyncio.to_thread(query.get)
    if docs:
        data = docs[0].to_dict()
        data["id"] = docs[0].id
        _deserialize_ts(data, ["createdAt", "updatedAt"])
        return data
    return None


# ---------------------------------------------------------------------------
# Aliases (backward-compat names used by orchestrators / routers)
# ---------------------------------------------------------------------------

get_zipcode_report = get_zipcode_research
get_run = get_zipcode_run
delete_run = delete_zipcode_run


async def get_multiple_runs(run_ids: list[str]) -> list[dict[str, Any]]:
    """Fetch multiple zipcode research runs by their IDs."""
    results = []
    for run_id in run_ids:
        doc = await get_zipcode_run(run_id)
        if doc:
            results.append(doc)
    return results
