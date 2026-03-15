"""Workflow dispatcher cron — starts the next queued workflow if none are active.

Runs every 5 minutes via Cloud Scheduler. Ensures only one workflow runs at a
time to stay within memory limits and optimize for cost.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Header, HTTPException

from hephae_api.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["workflow-dispatcher"])

# Phases that mean a workflow is actively consuming resources
_ACTIVE_PHASES = {"discovery", "qualification", "analysis", "evaluation", "outreach"}


@router.get("/api/cron/workflow-dispatcher")
async def workflow_dispatcher(
    authorization: str | None = Header(None),
    x_cron_secret: str | None = Header(None),
):
    """Start the next queued workflow if no workflow is currently active.

    Called by Cloud Scheduler every 5 minutes.
    """
    cron_token = x_cron_secret or authorization
    if settings.CRON_SECRET and cron_token != f"Bearer {settings.CRON_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    from hephae_db.firestore.workflows import list_workflows
    from hephae_api.types import WorkflowDocument, WorkflowPhase
    from hephae_api.workflows.engine import start_workflow_engine

    # Fetch recent workflows
    all_workflows = await list_workflows(limit=50, model_class=WorkflowDocument)

    # Check if any workflow is actively running
    active = [w for w in all_workflows if w.phase.value in _ACTIVE_PHASES]
    if active:
        active_info = [(w.id[:12], w.phase.value, w.businessType, w.zipCode) for w in active]
        logger.info(f"[Dispatcher] {len(active)} active workflow(s), skipping: {active_info}")
        return {
            "dispatched": False,
            "reason": "active_workflow_running",
            "activeCount": len(active),
            "activeWorkflows": [
                {"id": w.id, "phase": w.phase.value, "businessType": w.businessType, "zipCode": w.zipCode}
                for w in active
            ],
        }

    # Find the oldest queued workflow
    queued = [w for w in all_workflows if w.phase == WorkflowPhase.QUEUED]
    if not queued:
        logger.info("[Dispatcher] No queued workflows")
        return {"dispatched": False, "reason": "no_queued_workflows"}

    # Sort by createdAt ascending (oldest first)
    queued.sort(key=lambda w: w.createdAt)
    next_wf = queued[0]

    logger.info(
        f"[Dispatcher] Starting queued workflow: {next_wf.id} "
        f"({next_wf.businessType} in {next_wf.zipCode}), "
        f"{len(queued) - 1} remaining in queue"
    )

    # Set phase to DISCOVERY and start the engine
    next_wf.phase = WorkflowPhase.DISCOVERY
    from hephae_db.firestore.workflows import save_workflow
    await save_workflow(next_wf)
    await start_workflow_engine(next_wf.id)

    return {
        "dispatched": True,
        "workflowId": next_wf.id,
        "businessType": next_wf.businessType,
        "zipCode": next_wf.zipCode,
        "remainingQueued": len(queued) - 1,
    }
