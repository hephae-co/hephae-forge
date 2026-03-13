"""Analysis phase — enqueues Cloud Tasks per business and polls for completion."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Callable

_sleep = asyncio.sleep  # indirection for testability

from backend.workflows.agents.insights.insights_agent import generate_insights
from hephae_db.firestore.businesses import get_business
from hephae_db.firestore.tasks import (
    create_task, update_task, get_tasks_by_ids,
    STATUS_COMPLETED, STATUS_FAILED,
)
from hephae_common.firebase import get_db
from backend.types import BusinessWorkflowState, BusinessPhase
from backend.workflows.capabilities.registry import (
    get_enabled_capabilities, FullCapabilityDefinition,
)

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 3
MAX_POLL_DURATION_SECONDS = 2400  # 40 minutes — safety valve for stuck tasks
STUCK_TASK_THRESHOLD_SECONDS = 600  # 10 minutes with no substep change → mark failed

PROMOTE_KEYS = [
    "phone", "email", "emailStatus", "contactFormUrl", "contactFormStatus", "hours", "googleMapsUrl", "socialLinks",
    "logoUrl", "favicon", "primaryColor", "secondaryColor",
    "persona", "menuUrl", "competitors", "news", "validationReport",
]


async def _run_capability(
    slug: str, cap_def: FullCapabilityDefinition, identity: dict, **kwargs
) -> dict | None:
    """Call a capability runner directly (in-process, no HTTP)."""
    try:
        result = await cap_def.runner(identity, **kwargs)
        if result:
            return result
        logger.error(f"[Analysis] {cap_def.name} returned None for {slug}")
        return None
    except Exception as e:
        logger.error(f"[Analysis] {cap_def.name} error for {slug}: {e}")
        return None


async def run_single_business_analysis(slug: str) -> dict:
    """Run the full capability pipeline on a single business (standalone, no workflow)."""
    db = get_db()
    biz_data = await get_business(slug)
    if not biz_data:
        raise ValueError(f"Business {slug} not found")

    identity: dict[str, Any] = biz_data.get("identity", {
        "name": biz_data.get("name", ""),
        "address": biz_data.get("address", ""),
        "docId": slug,
    })
    if "docId" not in identity:
        identity["docId"] = slug

    zip_code = biz_data.get("zipCode")
    business_type = biz_data.get("businessType") or biz_data.get("category")

    if zip_code:
        try:
            from hephae_db.firestore.research import get_area_research_for_zip_code
            area_doc = await get_area_research_for_zip_code(zip_code)
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
                zip_doc = await get_zipcode_report(zip_code)
                if zip_doc and zip_doc.report:
                    report = zip_doc.report
                    sections = report.sections if hasattr(report, "sections") else None
                    if sections:
                        identity["zipCodeResearchContext"] = {
                            "zipCode": zip_code,
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

    enabled_capabilities = get_enabled_capabilities()
    official_url = biz_data.get("officialUrl") or identity.get("officialUrl")
    should_run_ctx = {**biz_data, **identity, "officialUrl": official_url}
    caps_to_run = [
        c for c in enabled_capabilities
        if not c.should_run or c.should_run(should_run_ctx)
    ]

    latest_outputs: dict[str, Any] = {}
    completed: list[str] = []
    failed: list[str] = []

    async def _run_cap(cap_def: FullCapabilityDefinition):
        raw = await _run_capability(slug, cap_def, identity)
        if raw:
            completed.append(cap_def.name)
            latest_outputs[cap_def.firestore_output_key] = cap_def.response_adapter(raw)
        else:
            failed.append(cap_def.name)

    await asyncio.gather(*[_run_cap(c) for c in caps_to_run], return_exceptions=True)

    if latest_outputs:
        try:
            await asyncio.to_thread(
                db.collection("businesses").document(slug).update,
                {"latestOutputs": latest_outputs, "updatedAt": datetime.utcnow()},
            )
        except Exception as e:
            logger.error(f"[Analysis] Firestore persist error for {slug}: {e}")

    insights = None
    try:
        insights = await generate_insights(slug)
    except Exception as e:
        logger.error(f"[Analysis] Insights error for {slug}: {e}")

    return {
        "capabilitiesCompleted": completed,
        "capabilitiesFailed": failed,
        "latestOutputs": latest_outputs,
        "insights": insights,
    }


async def run_analysis_phase(
    businesses: list[BusinessWorkflowState],
    callbacks: dict[str, Callable],
    workflow_id: str = "",
) -> None:
    """Enqueue Cloud Tasks per business and poll Firestore for completion."""
    from backend.lib.tasks import enqueue_agent_task

    pending = [b for b in businesses if b.phase in (BusinessPhase.PENDING, BusinessPhase.ENRICHING, BusinessPhase.ANALYZING)]
    if not pending:
        return

    biz_by_slug: dict[str, BusinessWorkflowState] = {b.slug: b for b in pending}

    # 1. Enqueue one WORKFLOW_ANALYZE Cloud Task per business
    task_map: dict[str, str] = {}  # task_id → slug
    for biz in pending:
        biz.phase = BusinessPhase.ENRICHING
        metadata = {
            "workflowId": workflow_id,
            "sourceZipCode": biz.sourceZipCode or "",
            "businessType": biz.businessType or "",
        }
        task_id = await create_task(
            biz.slug, "WORKFLOW_ANALYZE", triggered_by="workflow", metadata=metadata,
        )
        result = enqueue_agent_task(
            biz.slug, "WORKFLOW_ANALYZE", task_id,
            metadata=metadata,
            dispatch_deadline_seconds=1800,  # 30 min
        )
        if result is None:
            logger.error(f"[Analysis] Failed to enqueue Cloud Task for {biz.slug}")
            await update_task(task_id, {"status": STATUS_FAILED, "error": "Failed to enqueue to Cloud Tasks"})
            biz.phase = BusinessPhase.ANALYSIS_DONE
            if callbacks.get("onBusinessDone"):
                await callbacks["onBusinessDone"](biz.slug)
            continue
        task_map[task_id] = biz.slug

    if not task_map:
        return

    # 2. Poll loop — check all tasks every POLL_INTERVAL_SECONDS
    task_ids = list(task_map.keys())
    last_substep: dict[str, str] = {tid: "" for tid in task_ids}
    last_substep_time: dict[str, float] = {tid: time.monotonic() for tid in task_ids}
    terminal_statuses = {STATUS_COMPLETED, STATUS_FAILED}
    poll_start = time.monotonic()

    while True:
        await _sleep(POLL_INTERVAL_SECONDS)

        elapsed = time.monotonic() - poll_start
        if elapsed > MAX_POLL_DURATION_SECONDS:
            logger.error(f"[Analysis] Polling timeout after {elapsed:.0f}s — force-failing remaining tasks")
            for tid in task_ids:
                slug = task_map[tid]
                biz = biz_by_slug[slug]
                if biz.phase != BusinessPhase.ANALYSIS_DONE:
                    biz.lastError = "Analysis timed out (polling limit exceeded)"
                    biz.phase = BusinessPhase.ANALYSIS_DONE
                    await update_task(tid, {"status": STATUS_FAILED, "error": biz.lastError})
                    if callbacks.get("onBusinessDone"):
                        await callbacks["onBusinessDone"](slug)
            break

        tasks = await get_tasks_by_ids(task_ids)
        tasks_by_id = {t["id"]: t for t in tasks}

        all_terminal = True
        now = time.monotonic()
        for tid in task_ids:
            task = tasks_by_id.get(tid)
            if not task:
                continue

            slug = task_map[tid]
            biz = biz_by_slug[slug]
            status = task.get("status", "")
            meta = task.get("metadata", {})
            substep = meta.get("substep", "")

            if status not in terminal_statuses:
                all_terminal = False

            # Sync officialUrl from task metadata whenever available
            if meta.get("officialUrl") and not biz.officialUrl:
                biz.officialUrl = meta["officialUrl"]

            # Detect substep transitions and fire callbacks
            prev = last_substep.get(tid, "")
            if substep != prev:
                last_substep[tid] = substep
                last_substep_time[tid] = now

                if substep == "enrichment_done" and prev != "enrichment_done":
                    biz.phase = BusinessPhase.ANALYZING
                    if callbacks.get("onEnrichmentDone"):
                        callbacks["onEnrichmentDone"](slug, True)
                elif substep.startswith("capability_done:"):
                    cap_name = substep.split(":", 1)[1]
                    biz.capabilitiesCompleted = meta.get("capabilitiesCompleted", [])
                    biz.capabilitiesFailed = meta.get("capabilitiesFailed", [])
                    if callbacks.get("onCapabilityDone"):
                        callbacks["onCapabilityDone"](slug, cap_name, True)
                elif substep == "insights_done":
                    if callbacks.get("onInsightsDone"):
                        callbacks["onInsightsDone"](slug, True)

            # Detect stuck tasks — no progress for STUCK_TASK_THRESHOLD_SECONDS
            if status not in terminal_statuses and biz.phase != BusinessPhase.ANALYSIS_DONE:
                stale_duration = now - last_substep_time.get(tid, poll_start)
                if stale_duration > STUCK_TASK_THRESHOLD_SECONDS:
                    logger.error(f"[Analysis] Task {tid} for {slug} stuck for {stale_duration:.0f}s — marking failed")
                    biz.lastError = f"Analysis stuck (no progress for {int(stale_duration)}s)"
                    biz.phase = BusinessPhase.ANALYSIS_DONE
                    await update_task(tid, {"status": STATUS_FAILED, "error": biz.lastError})
                    if callbacks.get("onBusinessDone"):
                        await callbacks["onBusinessDone"](slug)
                    continue

            # Detect terminal status
            if status == STATUS_COMPLETED and biz.phase != BusinessPhase.ANALYSIS_DONE:
                biz.phase = BusinessPhase.ANALYSIS_DONE
                if callbacks.get("onBusinessDone"):
                    await callbacks["onBusinessDone"](slug)
            elif status == STATUS_FAILED and biz.phase != BusinessPhase.ANALYSIS_DONE:
                biz.lastError = task.get("error", "Unknown error")
                biz.phase = BusinessPhase.ANALYSIS_DONE
                if callbacks.get("onBusinessDone"):
                    await callbacks["onBusinessDone"](slug)

        if all_terminal:
            break
