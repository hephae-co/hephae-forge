"""Firestore persistence for test_fixtures collection."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from backend.lib.firebase import get_db
from backend.types import TestFixture, FixtureType

logger = logging.getLogger(__name__)

COLLECTION = "test_fixtures"


def _deserialize(doc_id: str, data: dict[str, Any]) -> TestFixture:
    data["id"] = doc_id
    for field in ("savedAt",):
        val = data.get(field)
        if val and hasattr(val, "seconds"):
            data[field] = datetime.utcfromtimestamp(val.seconds + val.nanoseconds / 1e9)
    return TestFixture.model_validate(data)


async def save_fixture(
    workflow_id: str,
    business_slug: str,
    fixture_type: str,
    notes: str | None = None,
    business_state: dict[str, Any] | None = None,
    identity: dict[str, Any] | None = None,
    latest_outputs: dict[str, Any] | None = None,
    source_zip_code: str | None = None,
    business_type: str | None = None,
) -> str:
    db = get_db()
    doc_ref = db.collection(COLLECTION).document()
    now = datetime.utcnow()

    data = {
        "fixtureType": fixture_type,
        "sourceWorkflowId": workflow_id,
        "sourceZipCode": source_zip_code,
        "businessType": business_type,
        "savedAt": now,
        "notes": notes,
        "businessState": business_state or {},
        "identity": identity or {"name": "", "address": "", "docId": business_slug},
        "latestOutputs": latest_outputs or {},
    }
    # Strip None values
    data = {k: v for k, v in data.items() if v is not None}

    await asyncio.to_thread(doc_ref.set, data)
    return doc_ref.id


async def save_fixture_from_business(
    business_slug: str,
    fixture_type: str,
    notes: str | None = None,
) -> str:
    """Save a fixture directly from a business document (without workflow context)."""
    db = get_db()
    biz_doc = await asyncio.to_thread(db.collection("businesses").document(business_slug).get)
    if not biz_doc.exists:
        raise ValueError(f"Business {business_slug} not found")

    biz_data = biz_doc.to_dict()
    return await save_fixture(
        workflow_id="",
        business_slug=business_slug,
        fixture_type=fixture_type,
        notes=notes,
        identity={
            "name": biz_data.get("name", ""),
            "address": biz_data.get("address", ""),
            "email": biz_data.get("email"),
            "socialLinks": biz_data.get("social"),
            "docId": business_slug,
        },
        latest_outputs=biz_data.get("latestOutputs", {}),
        source_zip_code=biz_data.get("zipCode"),
    )


async def list_fixtures(fixture_type: str | None = None) -> list[TestFixture]:
    db = get_db()
    query = db.collection(COLLECTION).order_by("savedAt", direction="DESCENDING")
    if fixture_type:
        query = query.where("fixtureType", "==", fixture_type)
    docs = await asyncio.to_thread(query.limit(50).get)
    return [_deserialize(doc.id, doc.to_dict()) for doc in docs]


async def get_fixture(fixture_id: str) -> TestFixture | None:
    db = get_db()
    doc = await asyncio.to_thread(db.collection(COLLECTION).document(fixture_id).get)
    if not doc.exists:
        return None
    return _deserialize(doc.id, doc.to_dict())


async def delete_fixture(fixture_id: str) -> None:
    db = get_db()
    await asyncio.to_thread(db.collection(COLLECTION).document(fixture_id).delete)
