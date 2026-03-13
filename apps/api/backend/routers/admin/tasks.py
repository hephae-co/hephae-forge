"""Task orchestration endpoints — spawn and execute background agentic tasks."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel

from backend.lib.auth import verify_admin_request
from backend.lib.tasks import enqueue_agent_task
from hephae_db.firestore.tasks import create_task, update_task, STATUS_RUNNING, STATUS_COMPLETED, STATUS_FAILED

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research/tasks", tags=["tasks"])

PROMOTE_KEYS = [
    "officialUrl", "phone", "email", "emailStatus", "contactFormUrl", "contactFormStatus", "hours", "googleMapsUrl", "socialLinks",
    "logoUrl", "favicon", "primaryColor", "secondaryColor",
    "persona", "menuUrl", "competitors", "news", "validationReport",
]

class SpawnTasksRequest(BaseModel):
    businessIds: list[str]
    actionType: str  # ENRICH, ANALYZE_FULL, SEO_AUDIT, etc.
    priority: int = 5

class ExecuteTaskRequest(BaseModel):
    businessId: str
    actionType: str
    taskId: str
    metadata: dict[str, Any] | None = None

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

    # 1. Mark as Running
    await update_task(req.taskId, {"status": STATUS_RUNNING, "startedAt": datetime.utcnow()})

    try:
        # WORKFLOW_ANALYZE: full pipeline for a single business within a workflow
        if req.actionType == "WORKFLOW_ANALYZE":
            result = await _run_workflow_analyze(req.businessId, req.taskId, req.metadata or {})
            await update_task(req.taskId, {
                "status": STATUS_COMPLETED,
                "completedAt": datetime.utcnow(),
                "progress": 100,
            })
            return {"success": True, "result": result}

        # 2. Agentic Dispatcher (The "Brain")
        # Decide what sub-actions are actually needed
        from backend.workflows.agents.discovery.dispatcher import plan_workflow
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
            elif a_type == "ANALYZE_FULL":
                await run_single_business_analysis(req.businessId)

        # 3. Mark as Completed
        await update_task(req.taskId, {"status": STATUS_COMPLETED, "completedAt": datetime.utcnow(), "progress": 100})
        return {"success": True, "plan": plan}

    except Exception as e:
        logger.error(f"[Tasks] Execution failed for {req.taskId}: {e}")
        await update_task(req.taskId, {"status": STATUS_FAILED, "error": str(e), "completedAt": datetime.utcnow()})
        raise HTTPException(status_code=500, detail=str(e))


async def _run_workflow_analyze(slug: str, task_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
    """Full analysis pipeline for a single business within a workflow Cloud Task."""
    from hephae_common.firebase import get_db
    from hephae_db.firestore.businesses import get_business
    from hephae_db.firestore.session_service import FirestoreSessionService
    from backend.workflows.phases.enrichment import enrich_business_profile
    from backend.workflows.capabilities.registry import get_enabled_capabilities, FullCapabilityDefinition
    from backend.workflows.phases.analysis import _run_capability
    from backend.workflows.agents.insights.insights_agent import generate_insights

    db = get_db()
    biz_data = await get_business(slug)
    if not biz_data:
        raise ValueError(f"Business {slug} not found")

    source_zip_code = metadata.get("sourceZipCode")
    business_type = metadata.get("businessType")

    async def _update_substep(substep: str, extra: dict[str, Any] | None = None):
        updates: dict[str, Any] = {f"metadata.substep": substep}
        if extra:
            for k, v in extra.items():
                updates[f"metadata.{k}"] = v
        await update_task(task_id, updates)

    # Store session prefix in task metadata for post-mortem debugging
    session_prefix = f"wf-{slug}-{int(time.time())}"
    await _update_substep("started", {"sessionPrefix": session_prefix})

    # Step 1: Enrichment
    name = biz_data.get("name", "")
    address = biz_data.get("address", "")
    enriched = None
    try:
        enriched = await enrich_business_profile(name, address, slug)
        if enriched:
            top_level = {k: enriched[k] for k in PROMOTE_KEYS if k in enriched}
            await asyncio.to_thread(
                db.collection("businesses").document(slug).update,
                {**top_level, "identity": {**enriched, "docId": slug}, "updatedAt": datetime.utcnow()},
            )
    except Exception as e:
        logger.error(f"[WorkflowAnalyze] Enrichment error for {slug}: {e}")

    # Step 2: Build identity from Firestore (refreshed after enrichment)
    biz_data = await get_business(slug)
    official_url = (biz_data or {}).get("officialUrl") or (biz_data or {}).get("identity", {}).get("officialUrl") or ""
    await _update_substep("enrichment_done", {"officialUrl": official_url})
    identity: dict[str, Any] = biz_data.get("identity", {
        "name": name, "address": address, "docId": slug,
    }) if biz_data else {"name": name, "address": address, "docId": slug}
    if "docId" not in identity:
        identity["docId"] = slug

    # Step 2b: Research context
    if source_zip_code:
        try:
            from hephae_db.firestore.research import get_area_research_for_zip_code
            area_doc = await get_area_research_for_zip_code(source_zip_code)
            if area_doc and area_doc.summary:
                summary = area_doc.summary
                identity["areaResearchContext"] = {
                    "areaName": area_doc.area,
                    "businessType": area_doc.businessType,
                    "resolvedState": area_doc.resolvedState or "",
                    "summary": summary.model_dump(mode="json") if hasattr(summary, "model_dump") else summary,
                }
        except Exception:
            pass

        if "areaResearchContext" not in identity:
            try:
                from hephae_db.firestore.research import get_zipcode_report
                zip_doc = await get_zipcode_report(source_zip_code)
                if zip_doc and zip_doc.report:
                    report = zip_doc.report
                    sections = report.sections if hasattr(report, "sections") else None
                    if sections:
                        identity["zipCodeResearchContext"] = {
                            "zipCode": source_zip_code,
                            "summary": report.summary if hasattr(report, "summary") else "",
                            "events": getattr(sections.events, "content", "") if sections.events else "",
                            "weather": getattr(sections.seasonal_weather, "content", "") if sections.seasonal_weather else "",
                            "demographics": getattr(sections.demographics, "content", "") if hasattr(sections, "demographics") else "",
                        }
            except Exception:
                pass

    if business_type:
        try:
            from hephae_db.firestore.research import get_sector_research_for_type
            sector_doc = await get_sector_research_for_type(business_type)
            if sector_doc and sector_doc.summary:
                summary = sector_doc.summary
                summary_dict = summary.model_dump(mode="json") if hasattr(summary, "model_dump") else summary
                identity["sectorResearchContext"] = {
                    "sector": sector_doc.sector,
                    "synthesis": summary_dict.get("synthesis", {}),
                    "industryAnalysis": summary_dict.get("industryAnalysis", {}),
                }
        except Exception:
            pass

    # Step 2c: Food pricing context
    if business_type:
        try:
            from hephae_integrations.fda_client import is_food_related_industry
            if is_food_related_industry(business_type):
                from hephae_integrations.bls_client import query_bls_cpi
                from hephae_integrations.usda_client import query_usda_prices

                state = ""
                area_ctx = identity.get("areaResearchContext")
                if isinstance(area_ctx, dict):
                    state = area_ctx.get("resolvedState", "")

                bls, usda = await asyncio.gather(
                    query_bls_cpi(business_type),
                    query_usda_prices(business_type, state),
                )

                identity["foodPricingContext"] = {
                    "blsHighlights": bls.highlights,
                    "usdaHighlights": usda.highlights,
                    "latestMonth": bls.latestMonth,
                    "source": "BLS Consumer Price Index + USDA NASS QuickStats",
                }
        except Exception as e:
            logger.warning(f"[WorkflowAnalyze] Food pricing context error for {slug}: {e}")

    # Step 3: Run capabilities
    enabled_capabilities = get_enabled_capabilities()
    official_url = (biz_data or {}).get("officialUrl") or identity.get("officialUrl")
    should_run_ctx = {**(biz_data or {}), **identity, "officialUrl": official_url}
    caps_to_run = [
        c for c in enabled_capabilities
        if not c.should_run or c.should_run(should_run_ctx)
    ]

    skipped = [c.name for c in enabled_capabilities if c not in caps_to_run]
    if skipped:
        logger.info(f"[WorkflowAnalyze] Skipping capabilities for {slug}: {skipped}")
        await _update_substep("capabilities_skipped", {"capabilitiesSkipped": skipped})

    latest_outputs: dict[str, Any] = {}
    completed: list[str] = []
    failed: list[str] = []

    # Shared Firestore session service for all capabilities — persists state for debugging
    wf_session_service = FirestoreSessionService()

    async def _run_cap(cap_def: FullCapabilityDefinition):
        raw = await _run_capability(slug, cap_def, identity, session_service=wf_session_service)
        if raw:
            completed.append(cap_def.name)
            latest_outputs[cap_def.firestore_output_key] = cap_def.response_adapter(raw)
        else:
            failed.append(cap_def.name)
        await _update_substep(f"capability_done:{cap_def.name}", {"capabilitiesCompleted": completed[:], "capabilitiesFailed": failed[:]})

    await asyncio.gather(*[_run_cap(c) for c in caps_to_run], return_exceptions=True)

    # Step 4: Persist latestOutputs
    if latest_outputs:
        try:
            await asyncio.to_thread(
                db.collection("businesses").document(slug).update,
                {"latestOutputs": latest_outputs, "updatedAt": datetime.utcnow()},
            )
        except Exception as e:
            logger.error(f"[WorkflowAnalyze] Firestore persist error for {slug}: {e}")

    # Step 5: Generate insights
    insights = None
    try:
        insights = await generate_insights(slug)
    except Exception as e:
        logger.error(f"[WorkflowAnalyze] Insights error for {slug}: {e}")

    await _update_substep("insights_done")

    return {
        "capabilitiesCompleted": completed,
        "capabilitiesFailed": failed,
        "insights": insights is not None,
    }
