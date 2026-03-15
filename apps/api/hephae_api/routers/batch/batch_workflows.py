"""Batch workflow trigger — queues workflows for sequential execution."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from hephae_api.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["batch-workflows"])


class BatchWorkflowRequest(BaseModel):
    jobs: list[dict]  # [{"zipCode": "07017", "businessType": "Restaurants"}, ...]


@router.post("/api/cron/batch-workflows")
async def batch_create_workflows(
    req: BatchWorkflowRequest,
    authorization: str | None = Header(None),
    x_cron_secret: str | None = Header(None),
):
    """Create workflows in QUEUED state for sequential processing.

    The workflow-dispatcher cron picks them up one at a time.
    """
    cron_token = x_cron_secret or authorization
    if settings.CRON_SECRET and cron_token != f"Bearer {settings.CRON_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    from hephae_db.firestore.workflows import create_workflow
    from hephae_api.types import WorkflowDocument, WorkflowPhase, WorkflowProgress

    results = []
    for job in req.jobs:
        zip_code = job.get("zipCode", "")
        business_type = job.get("businessType")

        if not zip_code:
            results.append({"error": "Missing zipCode", "job": job})
            continue

        try:
            workflow = await create_workflow(
                zip_code=zip_code,
                business_type=business_type,
                workflow_model=WorkflowDocument,
                phase_enum=WorkflowPhase,
                progress_model=WorkflowProgress,
            )
            # Override phase to QUEUED (create_workflow sets DISCOVERY by default)
            from hephae_db.firestore.workflows import save_workflow
            workflow.phase = WorkflowPhase.QUEUED
            await save_workflow(workflow)

            logger.info(f"[BatchWorkflows] Queued: {business_type} in {zip_code} → {workflow.id}")
            results.append({
                "workflowId": workflow.id,
                "zipCode": zip_code,
                "businessType": business_type,
                "status": "queued",
            })
        except Exception as e:
            logger.error(f"[BatchWorkflows] Failed to queue {business_type} in {zip_code}: {e}")
            results.append({
                "zipCode": zip_code,
                "businessType": business_type,
                "status": "error",
                "error": str(e),
            })

    queued = sum(1 for r in results if r.get("status") == "queued")
    failed = sum(1 for r in results if r.get("status") == "error")

    return {
        "total": len(req.jobs),
        "queued": queued,
        "failed": failed,
        "results": results,
    }
