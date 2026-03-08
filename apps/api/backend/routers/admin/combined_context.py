"""Combined context endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.workflows.agents.research.context_combiner import combine_research_context
from hephae_db.firestore.combined_context import (
    save_combined_context, get_combined_context, list_combined_contexts, delete_combined_context,
)
from hephae_db.firestore.research import get_multiple_runs
from backend.routers.admin import _serialize

router = APIRouter(prefix="/api/combined-context", tags=["combined-context"])


class CreateCombinedContextRequest(BaseModel):
    runIds: list[str]


@router.post("")
async def create_combined_context(req: CreateCombinedContextRequest):
    if len(req.runIds) < 2:
        raise HTTPException(status_code=400, detail="At least 2 run IDs required")

    # Fetch the reports
    runs = await get_multiple_runs(req.runIds)
    if len(runs) < 2:
        raise HTTPException(status_code=400, detail="Could not find enough valid runs")

    reports = []
    zip_codes = []
    for run in runs:
        report = run.get("report", {})
        report_dict = report.model_dump(mode="json") if hasattr(report, "model_dump") else report
        reports.append(report_dict)
        zip_codes.append(run.get("zipCode", ""))

    # Combine using agent
    context = await combine_research_context(reports)

    # Save
    context_id = await save_combined_context(req.runIds, zip_codes, context)

    return {"success": True, "contextId": context_id, "context": context}


@router.get("")
async def list_contexts(limit: int = Query(10, ge=1, le=50)):
    contexts = await list_combined_contexts(limit=limit)
    return [_serialize(c) for c in contexts]


@router.get("/{context_id}")
async def get_context(context_id: str):
    ctx = await get_combined_context(context_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Context not found")
    return _serialize(ctx)


@router.delete("/{context_id}")
async def delete_context(context_id: str):
    await delete_combined_context(context_id)
    return {"success": True}
