"""Firestore persistence for test_fixtures collection."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

COLLECTION = "test_fixtures"


def _deserialize_ts(data: dict[str, Any]) -> None:
    for field in ("savedAt",):
        val = data.get(field)
        if val and hasattr(val, "seconds"):
            data[field] = datetime.utcfromtimestamp(val.seconds + val.nanoseconds / 1e9)


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
    data = {k: v for k, v in data.items() if v is not None}

    await asyncio.to_thread(doc_ref.set, data)
    return doc_ref.id


async def save_fixture_from_business(
    business_slug: str,
    fixture_type: str,
    notes: str | None = None,
    agent_key: str | None = None,
    is_gold_standard: bool = False,
) -> str:
    db = get_db()
    biz_doc = await asyncio.to_thread(db.collection("businesses").document(business_slug).get)
    if not biz_doc.exists:
        raise ValueError(f"Business {business_slug} not found")

    biz_data = biz_doc.to_dict()
    latest_outputs = biz_data.get("latestOutputs", {})

    data = {
        "fixtureType": fixture_type,
        "isGoldStandard": is_gold_standard,
        "sourceWorkflowId": "",
        "sourceZipCode": biz_data.get("zipCode"),
        "businessType": biz_data.get("businessType"),
        "savedAt": datetime.utcnow(),
        "notes": notes,
        "identity": {
            "name": biz_data.get("name", ""),
            "address": biz_data.get("address", ""),
            "email": biz_data.get("email"),
            "officialUrl": biz_data.get("officialUrl"),
            "category": biz_data.get("category"),
            "socialLinks": biz_data.get("social"),
            "competitors": biz_data.get("competitors", []),
            "menuData": biz_data.get("menuData"),
            "coordinates": biz_data.get("coordinates"),
            "docId": business_slug,
        },
        "latestOutputs": latest_outputs,
        # Per-agent fields — populated when saving from a specific agent tab
        "agentKey": agent_key,
        "agentOutput": latest_outputs.get(agent_key) if agent_key else None,
    }
    data = {k: v for k, v in data.items() if v is not None}

    doc_ref = db.collection(COLLECTION).document()
    await asyncio.to_thread(doc_ref.set, data)

    # Track 2: Sync to Vertex AI Example Store if it's a Gold Standard example
    if is_gold_standard and agent_key:
        try:
            from hephae_db.eval.example_store import example_store
            store_id = f"{agent_key.replace('_', '-')}-store"
            # Extract input/output for the example
            input_text = f"Business: {biz_data.get('name')}, Category: {biz_data.get('category')}, Website: {biz_data.get('officialUrl')}"
            output_text = str(latest_outputs.get(agent_key, ""))
            
            await example_store.create_example(
                store_id=store_id,
                input_text=input_text,
                output_text=output_text,
                metadata={"sector": biz_data.get("category", "General"), "agent": agent_key}
            )
        except Exception as e:
            logger.warning(f"[Fixture] Failed to sync to Example Store: {e}")

    return doc_ref.id


async def list_fixtures(
    fixture_type: str | None = None,
    agent_key: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    db = get_db()
    query = db.collection(COLLECTION).order_by("savedAt", direction="DESCENDING")
    if fixture_type:
        query = query.where("fixtureType", "==", fixture_type)
    if agent_key:
        query = query.where("agentKey", "==", agent_key)
    docs = await asyncio.to_thread(query.limit(limit).get)
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        _deserialize_ts(data)
        results.append(data)
    return results


async def get_fixture(fixture_id: str) -> dict[str, Any] | None:
    db = get_db()
    doc = await asyncio.to_thread(db.collection(COLLECTION).document(fixture_id).get)
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["id"] = doc.id
    _deserialize_ts(data)
    return data


async def delete_fixture(fixture_id: str) -> None:
    db = get_db()
    await asyncio.to_thread(db.collection(COLLECTION).document(fixture_id).delete)
