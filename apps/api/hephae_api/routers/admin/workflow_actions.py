"""Workflow action endpoints — GET/PATCH/DELETE /api/workflows/{id}, approve, resume."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from hephae_api.lib.auth import verify_admin_request

from hephae_db.firestore.workflows import load_workflow, save_workflow, delete_workflow
from hephae_db.bigquery.feedback import record_approval_feedback
from hephae_api.types import WorkflowDocument, WorkflowPhase, BusinessPhase
from hephae_api.workflows.engine import WorkflowEngine, start_workflow_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflow-actions"], dependencies=[Depends(verify_admin_request)])


class ApproveRequest(BaseModel):
    approvals: dict[str, str]  # slug -> "approve" | "reject"


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str):
    workflow = await load_workflow(workflow_id, model_class=WorkflowDocument)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow.model_dump(mode="json")


@router.get("/{workflow_id}/research")
async def get_workflow_research(workflow_id: str):
    """Fetch zip code and area research produced during a workflow run."""
    workflow = await load_workflow(workflow_id, model_class=WorkflowDocument)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    from hephae_db.firestore.research import get_zipcode_report, get_area_research_for_zip_code

    zip_codes = workflow.zipCodes or ([workflow.zipCode] if workflow.zipCode else [])
    research: dict = {"zipReports": {}, "areaResearch": {}}

    for zc in zip_codes:
        try:
            zip_doc = await get_zipcode_report(zc)
            if zip_doc:
                report = zip_doc.get("report") if isinstance(zip_doc, dict) else getattr(zip_doc, "report", None)
                if report:
                    research["zipReports"][zc] = report.model_dump(mode="json") if hasattr(report, "model_dump") else report
        except Exception:
            pass

        try:
            area_doc = await get_area_research_for_zip_code(zc)
            if area_doc:
                summary = area_doc.get("summary") if isinstance(area_doc, dict) else getattr(area_doc, "summary", None)
                if summary:
                    area_name = area_doc.get("area", "") if isinstance(area_doc, dict) else getattr(area_doc, "area", "")
                    biz_type = area_doc.get("businessType", "") if isinstance(area_doc, dict) else getattr(area_doc, "businessType", "")
                    research["areaResearch"][zc] = {
                        "area": area_name,
                        "businessType": biz_type,
                        "summary": summary.model_dump(mode="json") if hasattr(summary, "model_dump") else summary,
                    }
        except Exception:
            pass

    return research


@router.patch("/{workflow_id}")
async def force_stop_workflow(workflow_id: str):
    """Force-stop a running workflow by marking it as failed."""
    workflow = await load_workflow(workflow_id, model_class=WorkflowDocument)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow.phase = WorkflowPhase.FAILED
    workflow.lastError = "Manually stopped by user"
    await save_workflow(workflow)

    return {"success": True, "message": "Workflow stopped"}


@router.delete("/{workflow_id}")
async def delete_workflow_endpoint(workflow_id: str, force: bool = Query(False)):
    try:
        result = await delete_workflow(workflow_id, model_class=WorkflowDocument, force=force)
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{workflow_id}/approve")
async def approve_workflow(workflow_id: str, req: ApproveRequest):
    workflow = await load_workflow(workflow_id, model_class=WorkflowDocument)
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

        # Record approval feedback to BigQuery (fire-and-forget)
        if decision in ("approve", "reject"):
            asyncio.create_task(record_approval_feedback(
                business_slug=biz.slug,
                human_decision=decision,
                auto_approved=False,
                zip_code=biz.sourceZipCode or "",
                business_type=biz.businessType or "",
            ))

    await save_workflow(workflow)

    if any_approved:
        # Start outreach engine in background
        engine = WorkflowEngine(workflow)
        asyncio.create_task(engine.resume_from_outreach())

    return {"success": True, "approved": any_approved}


@router.post("/{workflow_id}/resume")
async def resume_workflow(workflow_id: str):
    workflow = await load_workflow(workflow_id, model_class=WorkflowDocument)
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
