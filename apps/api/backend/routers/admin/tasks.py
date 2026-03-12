"""Task orchestration endpoints — spawn and execute background agentic tasks."""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel

from backend.lib.auth import verify_admin_request
from backend.lib.tasks import enqueue_agent_task
from hephae_db.firestore.tasks import create_task, update_task, STATUS_RUNNING, STATUS_COMPLETED, STATUS_FAILED

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research/tasks", tags=["tasks"])

class SpawnTasksRequest(BaseModel):
    businessIds: list[str]
    actionType: str  # ENRICH, ANALYZE_FULL, SEO_AUDIT, etc.
    priority: int = 5

class ExecuteTaskRequest(BaseModel):
    businessId: str
    actionType: str
    taskId: str

@router.get("", dependencies=[Depends(verify_admin_request)])
async def list_tasks(businessIds: str = Query(...)):
    """Fetch recent tasks for a comma-separated list of business IDs."""
    ids = [i.strip() for i in businessIds.split(",") if i.strip()]
    from hephae_db.firestore.tasks import list_active_tasks_for_businesses
    tasks = await list_active_tasks_for_businesses(ids)
    
    # Simple serialization helper
    for t in tasks:
        for field in ("createdAt", "startedAt", "completedAt"):
            val = t.get(field)
            if val and hasattr(val, "isoformat"):
                t[field] = val.isoformat()
                
    return {"tasks": tasks}

@router.post("/spawn", dependencies=[Depends(verify_admin_request)])
async def spawn_tasks(req: SpawnTasksRequest):
    """Bulk spawn tasks into the Cloud Tasks queue."""
    task_ids = []
    enqueue_failures = 0
    for biz_id in req.businessIds:
        # 1. Create Ledger Entry
        task_id = await create_task(biz_id, req.actionType, priority=req.priority)

        # 2. Enqueue in Cloud Tasks
        result = enqueue_agent_task(biz_id, req.actionType, task_id, req.priority)
        if result is None:
            enqueue_failures += 1
            await update_task(task_id, {"status": STATUS_FAILED, "error": "Failed to enqueue to Cloud Tasks"})
        task_ids.append(task_id)

    if enqueue_failures == len(req.businessIds):
        raise HTTPException(
            status_code=503,
            detail="Cloud Tasks queue unavailable — no tasks could be enqueued",
        )

    return {
        "success": True,
        "count": len(task_ids),
        "taskIds": task_ids,
        "enqueueFailed": enqueue_failures,
    }

@router.post("/execute")
async def execute_task(req: ExecuteTaskRequest):
    """The internal endpoint called by Cloud Tasks to run the actual agent."""
    from datetime import datetime
    from backend.workflows.agents.discovery.dispatcher import plan_workflow
    
    # 1. Mark as Running
    await update_task(req.taskId, {"status": STATUS_RUNNING, "startedAt": datetime.utcnow()})
    
    try:
        # 2. Agentic Dispatcher (The "Brain")
        # Decide what sub-actions are actually needed
        plan = await plan_workflow(req.businessId, req.actionType)
        logger.info(f"[Dispatcher] Rationale: {plan.get('rationale')}")
        
        from backend.workflows.phases.analysis import run_single_business_analysis, _run_capability
        from backend.workflows.phases.enrichment import enrich_business_profile
        from backend.workflows.capabilities.registry import get_capability
        from hephae_db.firestore.businesses import get_business
        
        biz = await get_business(req.businessId)
        identity = biz.get("identity")
        
        for action in plan.get("actions", []):
            a_type = action["type"]
            if a_type == "ENRICH":
                identity = await enrich_business_profile(biz["name"], biz.get("address", ""), req.businessId)
            elif a_type == "SEO":
                cap = get_capability("seo")
                if cap and identity: await _run_capability(req.businessId, cap, identity)
            elif a_type == "MARGIN":
                cap = get_capability("margin_surgeon")
                if cap and identity: await _run_capability(req.businessId, cap, identity)
            # ... add other mapping here or use run_single_business_analysis
            elif a_type == "ANALYZE_FULL":
                await run_single_business_analysis(req.businessId)
            
        # 3. Mark as Completed
        await update_task(req.taskId, {"status": STATUS_COMPLETED, "completedAt": datetime.utcnow(), "progress": 100})
        return {"success": True, "plan": plan}
        
    except Exception as e:
        logger.error(f"[Tasks] Execution failed for {req.taskId}: {e}")
        await update_task(req.taskId, {"status": STATUS_FAILED, "error": str(e), "completedAt": datetime.utcnow()})
        raise HTTPException(status_code=500, detail=str(e))
