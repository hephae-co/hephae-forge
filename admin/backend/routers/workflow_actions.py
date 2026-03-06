"""Workflow action endpoints — GET/PATCH/DELETE /api/workflows/{id}, approve, resume."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.lib.db.workflows import load_workflow, save_workflow, delete_workflow
from backend.types import WorkflowPhase, BusinessPhase
from backend.workflow.engine import WorkflowEngine, start_workflow_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflow-actions"])


class ApproveRequest(BaseModel):
    approvals: dict[str, str]  # slug -> "approve" | "reject"


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str):
    workflow = await load_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow.model_dump(mode="json")


@router.patch("/{workflow_id}")
async def force_stop_workflow(workflow_id: str):
    """Force-stop a running workflow by marking it as failed."""
    workflow = await load_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow.phase = WorkflowPhase.FAILED
    workflow.lastError = "Manually stopped by user"
    await save_workflow(workflow)

    return {"success": True, "message": "Workflow stopped"}


@router.delete("/{workflow_id}")
async def delete_workflow_endpoint(workflow_id: str, force: bool = Query(False)):
    try:
        result = await delete_workflow(workflow_id, force=force)
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{workflow_id}/approve")
async def approve_workflow(workflow_id: str, req: ApproveRequest):
    workflow = await load_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if workflow.phase != WorkflowPhase.APPROVAL:
        raise HTTPException(status_code=400, detail=f"Workflow is in {workflow.phase.value} phase, not approval")

    # Apply approvals/rejections
    any_approved = False
    for biz in workflow.businesses:
        decision = req.approvals.get(biz.slug)
        if decision == "approve":
            biz.phase = BusinessPhase.APPROVED
            any_approved = True
        elif decision == "reject":
            biz.phase = BusinessPhase.REJECTED

    await save_workflow(workflow)

    if any_approved:
        # Start outreach engine in background
        engine = WorkflowEngine(workflow)
        asyncio.create_task(engine.resume_from_outreach())

    return {"success": True, "approved": any_approved}


@router.post("/{workflow_id}/resume")
async def resume_workflow(workflow_id: str):
    workflow = await load_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if workflow.phase != WorkflowPhase.FAILED:
        raise HTTPException(status_code=400, detail="Can only resume failed workflows")

    # Clear error and increment retry
    workflow.lastError = None
    workflow.retryCount += 1

    # Determine resume phase based on business states
    has_analysis_done = any(
        b.phase in (BusinessPhase.ANALYSIS_DONE, BusinessPhase.EVALUATING, BusinessPhase.EVALUATION_DONE)
        for b in workflow.businesses
    )
    has_eval_done = any(
        b.phase in (BusinessPhase.EVALUATION_DONE, BusinessPhase.APPROVED, BusinessPhase.REJECTED)
        for b in workflow.businesses
    )

    if has_eval_done:
        workflow.phase = WorkflowPhase.EVALUATION
    elif has_analysis_done:
        workflow.phase = WorkflowPhase.ANALYSIS
    else:
        workflow.phase = WorkflowPhase.DISCOVERY

    await save_workflow(workflow)
    await start_workflow_engine(workflow_id)

    return {"success": True, "resumePhase": workflow.phase.value}
