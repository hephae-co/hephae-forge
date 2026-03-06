"""Firestore persistence for workflows collection."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from backend.lib.firebase import get_db
from backend.types import (
    WorkflowDocument, WorkflowPhase, WorkflowProgress,
    BusinessWorkflowState, BusinessPhase, EvaluationResult, BusinessInsights,
)

logger = logging.getLogger(__name__)

COLLECTION = "workflows"
ACTIVE_PHASES = [WorkflowPhase.DISCOVERY, WorkflowPhase.ANALYSIS, WorkflowPhase.EVALUATION, WorkflowPhase.OUTREACH]


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


def _serialize(workflow: WorkflowDocument) -> dict[str, Any]:
    data = workflow.model_dump(mode="json")
    return _strip_none(data)


def _deserialize(doc_id: str, data: dict[str, Any]) -> WorkflowDocument:
    data["id"] = doc_id
    # Convert Firestore Timestamps to datetime
    for field in ("createdAt", "updatedAt"):
        val = data.get(field)
        if val and hasattr(val, "isoformat"):
            pass  # already datetime-like
        elif val and hasattr(val, "seconds"):
            data[field] = datetime.utcfromtimestamp(val.seconds + val.nanoseconds / 1e9)
    return WorkflowDocument.model_validate(data)


async def create_workflow(
    zip_code: str = "",
    business_type: str | None = None,
    county: str | None = None,
    zip_codes: list[str] | None = None,
) -> WorkflowDocument:
    db = get_db()
    doc_ref = db.collection(COLLECTION).document()
    now = datetime.utcnow()

    resolved_from = "county" if county else "single"
    if not zip_code and zip_codes:
        zip_code = zip_codes[0]

    workflow = WorkflowDocument(
        id=doc_ref.id,
        zipCode=zip_code,
        businessType=business_type,
        county=county,
        zipCodes=zip_codes,
        resolvedFrom=resolved_from,
        phase=WorkflowPhase.DISCOVERY,
        createdAt=now,
        updatedAt=now,
        businesses=[],
        progress=WorkflowProgress(),
        retryCount=0,
    )

    await asyncio.to_thread(doc_ref.set, _serialize(workflow))
    return workflow


async def save_workflow(workflow: WorkflowDocument) -> None:
    db = get_db()
    workflow.updatedAt = datetime.utcnow()
    await asyncio.to_thread(
        db.collection(COLLECTION).document(workflow.id).set,
        _serialize(workflow),
    )


async def load_workflow(workflow_id: str) -> WorkflowDocument | None:
    db = get_db()
    doc = await asyncio.to_thread(db.collection(COLLECTION).document(workflow_id).get)
    if not doc.exists:
        return None
    return _deserialize(doc.id, doc.to_dict())


async def list_workflows(limit: int = 20) -> list[WorkflowDocument]:
    db = get_db()
    query = db.collection(COLLECTION).order_by("createdAt", direction="DESCENDING").limit(limit)
    docs = await asyncio.to_thread(query.get)
    return [_deserialize(doc.id, doc.to_dict()) for doc in docs]


async def delete_workflow(workflow_id: str, force: bool = False) -> dict[str, int]:
    workflow = await load_workflow(workflow_id)
    if not workflow:
        raise ValueError("Workflow not found")

    if not force and workflow.phase in ACTIVE_PHASES:
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


def recompute_progress(workflow: WorkflowDocument) -> None:
    """Recompute progress counters from business states."""
    businesses = workflow.businesses
    post_analysis = {
        BusinessPhase.ANALYSIS_DONE, BusinessPhase.EVALUATING, BusinessPhase.EVALUATION_DONE,
        BusinessPhase.APPROVED, BusinessPhase.REJECTED, BusinessPhase.OUTREACHING,
        BusinessPhase.OUTREACH_DONE, BusinessPhase.OUTREACH_FAILED,
    }
    post_evaluation = {
        BusinessPhase.EVALUATION_DONE, BusinessPhase.APPROVED, BusinessPhase.REJECTED,
        BusinessPhase.OUTREACHING, BusinessPhase.OUTREACH_DONE, BusinessPhase.OUTREACH_FAILED,
    }
    approved_set = {
        BusinessPhase.APPROVED, BusinessPhase.OUTREACHING,
        BusinessPhase.OUTREACH_DONE, BusinessPhase.OUTREACH_FAILED,
    }

    workflow.progress = WorkflowProgress(
        totalBusinesses=len(businesses),
        analysisComplete=sum(1 for b in businesses if b.phase in post_analysis),
        evaluationComplete=sum(1 for b in businesses if b.phase in post_evaluation),
        qualityPassed=sum(1 for b in businesses if b.qualityPassed),
        qualityFailed=sum(
            1 for b in businesses
            if b.phase in {BusinessPhase.EVALUATION_DONE, BusinessPhase.REJECTED} and not b.qualityPassed
        ),
        approved=sum(1 for b in businesses if b.phase in approved_set),
        outreachComplete=sum(1 for b in businesses if b.phase == BusinessPhase.OUTREACH_DONE),
        insightsComplete=sum(1 for b in businesses if b.insights is not None),
    )
