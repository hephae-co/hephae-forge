"""Batch workflow trigger — kick off multiple workflows via CRON_SECRET auth."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from hephae_api.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["batch-workflows"])


class BatchWorkflowRequest(BaseModel):
    jobs: list[dict]  # [{"zipCode": "07017", "businessType": "Restaurants"}, ...]
    delay_seconds: int = 10  # delay between workflow launches


@router.post("/api/cron/batch-workflows")
async def batch_create_workflows(
    req: BatchWorkflowRequest,
    authorization: str | None = Header(None),
    x_cron_secret: str | None = Header(None),
):
    """Create and start multiple workflows. Auth via CRON_SECRET.

    Accepts CRON_SECRET in either Authorization header (Cloud Scheduler)
    or X-Cron-Secret header (CLI calls where Authorization is used by Cloud Run IAM).
    """
    cron_token = x_cron_secret or authorization
    if settings.CRON_SECRET and cron_token != f"Bearer {settings.CRON_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    from hephae_db.firestore.workflows import create_workflow
    from hephae_api.types import WorkflowDocument, WorkflowPhase, WorkflowProgress
    from hephae_api.workflows.engine import start_workflow_engine

    results = []
    for i, job in enumerate(req.jobs):
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
            await start_workflow_engine(workflow.id)
            logger.info(f"[BatchWorkflows] Started {i+1}/{len(req.jobs)}: {business_type} in {zip_code} → {workflow.id}")
            results.append({
                "workflowId": workflow.id,
                "zipCode": zip_code,
                "businessType": business_type,
                "status": "started",
            })
        except Exception as e:
            logger.error(f"[BatchWorkflows] Failed to start {business_type} in {zip_code}: {e}")
            results.append({
                "zipCode": zip_code,
                "businessType": business_type,
                "status": "error",
                "error": str(e),
            })

        # Stagger launches to avoid rate limits
        if i < len(req.jobs) - 1 and req.delay_seconds > 0:
            await asyncio.sleep(req.delay_seconds)

    started = sum(1 for r in results if r.get("status") == "started")
    failed = sum(1 for r in results if r.get("status") == "error")

    return {
        "total": len(req.jobs),
        "started": started,
        "failed": failed,
        "results": results,
    }
