"""Firestore persistence for workflows collection.

NOTE: This module uses admin-specific Pydantic types. During Phase 1,
these are imported lazily to avoid circular dependencies. In Phase 2,
types will be unified in the api service.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, TYPE_CHECKING

from hephae_common.firebase import get_db

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

COLLECTION = "workflows"


def _strip_none(obj: dict) -> dict:
    """Recursively remove None values from dict (Firestore rejects undefined)."""
    cleaned = {}
    for k, v in obj.items():
        if v is None:
            continue
        if isinstance(v, dict):
            cleaned[k] = _strip_none(v)
        elif isinstance(v, list):
            cleaned[k] = [_strip_none(item) if isinstance(item, dict) else item for item in v]
        else:
            cleaned[k] = v
    return cleaned


def _serialize(workflow: Any) -> dict[str, Any]:
    data = workflow.model_dump(mode="json")
    return _strip_none(data)


def _deserialize(doc_id: str, data: dict[str, Any], model_class: type) -> Any:
    data["id"] = doc_id
    for field in ("createdAt", "updatedAt"):
        val = data.get(field)
        if val and hasattr(val, "seconds"):
            data[field] = datetime.utcfromtimestamp(val.seconds + val.nanoseconds / 1e9)
    return model_class.model_validate(data)


async def create_workflow(
    zip_code: str = "",
    business_type: str | None = None,
    county: str | None = None,
    zip_codes: list[str] | None = None,
    *,
    workflow_model: type | None = None,
    phase_enum: type | None = None,
    progress_model: type | None = None,
) -> Any:
    """Create a new workflow document.

    Pass workflow_model, phase_enum, progress_model from your app's types module.
    """
    db = get_db()
    doc_ref = db.collection(COLLECTION).document()
    now = datetime.utcnow()

    resolved_from = "county" if county else "single"
    if not zip_code and zip_codes:
        zip_code = zip_codes[0]

    workflow = workflow_model(
        id=doc_ref.id,
        zipCode=zip_code,
        businessType=business_type,
        county=county,
        zipCodes=zip_codes,
        resolvedFrom=resolved_from,
        phase=phase_enum.DISCOVERY if phase_enum else "discovery",
        createdAt=now,
        updatedAt=now,
        businesses=[],
        progress=progress_model() if progress_model else {},
        retryCount=0,
    )

    await asyncio.to_thread(doc_ref.set, _serialize(workflow))
    return workflow


async def save_workflow(workflow: Any) -> None:
    db = get_db()
    workflow.updatedAt = datetime.utcnow()
    await asyncio.to_thread(
        db.collection(COLLECTION).document(workflow.id).set,
        _serialize(workflow),
    )


async def load_workflow(workflow_id: str, *, model_class: type) -> Any | None:
    db = get_db()
    doc = await asyncio.to_thread(db.collection(COLLECTION).document(workflow_id).get)
    if not doc.exists:
        return None
    return _deserialize(doc.id, doc.to_dict(), model_class)


async def list_workflows(limit: int = 20, *, model_class: type) -> list[Any]:
    db = get_db()
    query = db.collection(COLLECTION).order_by("createdAt", direction="DESCENDING").limit(limit)
    docs = await asyncio.to_thread(query.get)
    return [_deserialize(doc.id, doc.to_dict(), model_class) for doc in docs]


async def delete_workflow(workflow_id: str, *, model_class: type, active_phases: list | None = None, force: bool = False) -> dict[str, int]:
    workflow = await load_workflow(workflow_id, model_class=model_class)
    if not workflow:
        raise ValueError("Workflow not found")

    if not force and active_phases and workflow.phase in active_phases:
        raise ValueError("Cannot delete a workflow that is actively running")

    db = get_db()
    slugs = [b.slug for b in workflow.businesses]
    businesses_removed = 0

    batch_size = 499
    for i in range(0, len(slugs), batch_size):
        batch = db.batch()
        chunk = slugs[i : i + batch_size]
        for slug in chunk:
            batch.delete(db.collection("businesses").document(slug))
            businesses_removed += 1
        await asyncio.to_thread(batch.commit)

    await asyncio.to_thread(db.collection(COLLECTION).document(workflow_id).delete)
    return {"businessesRemoved": businesses_removed}


def recompute_progress(workflow: Any, *, phase_enum: type, progress_model: type) -> None:
    """Recompute progress counters from business states."""
    businesses = workflow.businesses
    post_analysis = {
        phase_enum.ANALYSIS_DONE, phase_enum.EVALUATING, phase_enum.EVALUATION_DONE,
        phase_enum.APPROVED, phase_enum.REJECTED, phase_enum.OUTREACHING,
        phase_enum.OUTREACH_DONE, phase_enum.OUTREACH_FAILED,
    }
    post_evaluation = {
        phase_enum.EVALUATION_DONE, phase_enum.APPROVED, phase_enum.REJECTED,
        phase_enum.OUTREACHING, phase_enum.OUTREACH_DONE, phase_enum.OUTREACH_FAILED,
    }
    approved_set = {
        phase_enum.APPROVED, phase_enum.OUTREACHING,
        phase_enum.OUTREACH_DONE, phase_enum.OUTREACH_FAILED,
    }

    workflow.progress = progress_model(
        totalBusinesses=len(businesses),
        analysisComplete=sum(1 for b in businesses if b.phase in post_analysis),
        evaluationComplete=sum(1 for b in businesses if b.phase in post_evaluation),
        qualityPassed=sum(1 for b in businesses if b.qualityPassed),
        qualityFailed=sum(
            1 for b in businesses
            if b.phase in {phase_enum.EVALUATION_DONE, phase_enum.REJECTED} and not b.qualityPassed
        ),
        approved=sum(1 for b in businesses if b.phase in approved_set),
        outreachComplete=sum(1 for b in businesses if b.phase == phase_enum.OUTREACH_DONE),
        insightsComplete=sum(1 for b in businesses if b.insights is not None),
    )
