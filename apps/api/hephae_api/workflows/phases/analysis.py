"""Analysis phase — enqueues Cloud Tasks per business and polls for completion."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Callable

_sleep = asyncio.sleep  # indirection for testability

from hephae_agents.insights.insights_agent import generate_insights
from hephae_db.firestore.businesses import get_business
from hephae_db.firestore.tasks import (
    create_task, update_task, get_tasks_by_ids,
    STATUS_COMPLETED, STATUS_FAILED, STATUS_RETRY_QUEUED,
)
from hephae_common.firebase import get_db
from hephae_api.types import BusinessWorkflowState, BusinessPhase
from hephae_api.workflows.capabilities.registry import (
    get_enabled_capabilities, FullCapabilityDefinition,
)

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 3
MAX_POLL_DURATION_SECONDS = 2400  # 40 minutes — safety valve for stuck tasks
STUCK_TASK_THRESHOLD_SECONDS = 600  # 10 minutes with no substep change → mark failed

# Retry configuration for retriable errors (429, 503, 529)
_CAP_MAX_RETRIES = 3
_CAP_RETRY_BACKOFF = [10, 30, 60]  # seconds between retries

PROMOTE_KEYS = [
    "phone", "email", "emailStatus", "contactFormUrl", "contactFormStatus", "hours", "googleMapsUrl", "socialLinks",
    "logoUrl", "favicon", "primaryColor", "secondaryColor",
    "persona", "menuUrl", "competitors", "news", "validationReport",
]


class RetriableCapabilityError(Exception):
    """Raised when a capability fails with a retriable error after exhausting retries."""
    pass


def _is_retriable_error(exc: Exception) -> bool:
    """Check if an exception is a retriable API error (429, 503, 529)."""
    msg = str(exc)
    return any(code in msg for code in ("429", "503", "529", "Resource exhausted", "RESOURCE_EXHAUSTED"))


async def _run_capability(
    slug: str, cap_def: FullCapabilityDefinition, identity: dict, **kwargs
) -> dict | None:
    """Call a capability runner with retry on 429/503/529 errors."""
    last_error = None
    for attempt in range(_CAP_MAX_RETRIES):
        try:
            result = await cap_def.runner(identity, **kwargs)
            if result:
                return result
            logger.error(f"[Analysis] {cap_def.name} returned None for {slug}")
            return None
        except Exception as e:
            last_error = e
            if _is_retriable_error(e) and attempt < _CAP_MAX_RETRIES - 1:
                wait = _CAP_RETRY_BACKOFF[min(attempt, len(_CAP_RETRY_BACKOFF) - 1)]
                logger.warning(f"[Analysis] {cap_def.name} retriable error for {slug} (attempt {attempt + 1}/{_CAP_MAX_RETRIES}): {e}, retrying in {wait}s")
                await asyncio.sleep(wait)
                continue
            if _is_retriable_error(e):
                logger.error(f"[Analysis] {cap_def.name} retriable error for {slug} after {_CAP_MAX_RETRIES} attempts: {e}")
                raise RetriableCapabilityError(f"{cap_def.name}: {e}") from e
            logger.error(f"[Analysis] {cap_def.name} error for {slug}: {e}")
            return None
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

    def _g(doc, key):
        return doc.get(key) if isinstance(doc, dict) else getattr(doc, key, None)

    if zip_code:
        try:
            from hephae_db.firestore.research import get_area_research_for_zip_code
            area_doc = await get_area_research_for_zip_code(zip_code)
            if area_doc:
                summary = _g(area_doc, "summary")
                if summary:
                    identity["areaResearchContext"] = {
                        "areaName": _g(area_doc, "area") or "",
                        "businessType": _g(area_doc, "businessType") or "",
                        "resolvedState": _g(area_doc, "resolvedState") or "",
                        "summary": summary.model_dump(mode="json") if hasattr(summary, "model_dump") else summary,
                    }
        except Exception:
            pass

        if "areaResearchContext" not in identity:
            try:
                from hephae_db.firestore.research import get_zipcode_report
                zip_doc = await get_zipcode_report(zip_code)
                if zip_doc:
                    report = _g(zip_doc, "report")
                    if report:
                        sections = _g(report, "sections") if not isinstance(report, dict) else report.get("sections")
                        if sections:
                            _sg = lambda s, k: (s.get(k) if isinstance(s, dict) else getattr(s, k, None))
                            events = _sg(sections, "events")
                            weather = _sg(sections, "seasonal_weather")
                            demographics = _sg(sections, "demographics")
                            identity["zipCodeResearchContext"] = {
                                "zipCode": zip_code,
                                "summary": _g(report, "summary") or "",
                                "events": (_g(events, "content") or "") if events else "",
                                "weather": (_g(weather, "content") or "") if weather else "",
                                "demographics": (_g(demographics, "content") or "") if demographics else "",
                            }
            except Exception:
                pass

    if business_type:
        try:
            from hephae_db.firestore.research import get_sector_research_for_type
            sector_doc = await get_sector_research_for_type(business_type)
            if sector_doc:
                summary = _g(sector_doc, "summary")
                if summary:
                    summary_dict = summary.model_dump(mode="json") if hasattr(summary, "model_dump") else (summary if isinstance(summary, dict) else {})
                    identity["sectorResearchContext"] = {
                        "sector": _g(sector_doc, "sector") or "",
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
    from hephae_api.lib.tasks import enqueue_agent_task

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
            "slug": biz.slug,
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

            if status not in terminal_statuses and status != STATUS_RETRY_QUEUED:
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
            if status not in terminal_statuses and status != STATUS_RETRY_QUEUED and biz.phase != BusinessPhase.ANALYSIS_DONE:
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
            elif status == STATUS_RETRY_QUEUED and biz.phase != BusinessPhase.ANALYSIS_DONE:
                # Partial success — some caps completed, others will retry in background.
                # Track the retry task and add it to our poll list.
                retry_task_id = meta.get("retryTaskId")
                retriable_failures = meta.get("retriableFailures", [])
                if retry_task_id and retry_task_id not in task_map:
                    task_map[retry_task_id] = slug
                    task_ids.append(retry_task_id)
                    last_substep[retry_task_id] = ""
                    last_substep_time[retry_task_id] = now
                    logger.info(f"[Analysis] Tracking retry task {retry_task_id} for {slug} (caps: {retriable_failures})")
                    if callbacks.get("onCapabilityDone"):
                        callbacks["onCapabilityDone"](slug, f"retry_queued({','.join(retriable_failures)})", True)

        if all_terminal:
            break

    # ── Final reconciliation pass ──────────────────────────────────────────
    # Ensure every business has been marked ANALYSIS_DONE even if the poller
    # missed a transition (e.g. task completed between the last poll check
    # and the all_terminal break).
    tasks = await get_tasks_by_ids(task_ids)
    tasks_by_id = {t["id"]: t for t in tasks}
    for tid in task_ids:
        task = tasks_by_id.get(tid)
        slug = task_map[tid]
        biz = biz_by_slug[slug]
        if biz.phase == BusinessPhase.ANALYSIS_DONE:
            continue
        status = (task or {}).get("status", "")
        if status in terminal_statuses or status == STATUS_RETRY_QUEUED or task is None:
            biz.phase = BusinessPhase.ANALYSIS_DONE
            if status == STATUS_FAILED:
                biz.lastError = (task or {}).get("error", "Unknown error")
            logger.info(f"[Analysis] Reconciliation: marked {slug} as ANALYSIS_DONE (status={status})")
            if callbacks.get("onBusinessDone"):
                await callbacks["onBusinessDone"](slug)
