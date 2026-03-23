"""Scheduled discovery orchestrator — marketing outreach discovery.

Entry point for the discovery-batch Cloud Run Job. On each execution:
  1. Claims the oldest pending job from Firestore
  2. For each target zip code:
     a. Scans for businesses (existing ADK zipcode scanner)
     b. Filters out recently-discovered businesses (freshness check)
     c. For each remaining business:
        - Runs the discovery pipeline (extracts contact details for marketing)
        - Passes through QualityGateAgent (discard chains, no-contact businesses)
        - Rate-limits between businesses
  3. Sends a completion email to the job's notify_email

Purpose: Discover businesses and collect contact details (name, address, phone,
email, website, social links) for marketing outreach. No capability analysis is
run — that is reserved for authenticated users via the profile builder flow.

Cost profile:
  - Sequential processing (no parallelism) — predictable, minimal compute cost
  - PRIMARY_MODEL only — cheapest Gemini tier
  - Freshness checks skip businesses we've already processed recently
  - Quality gate eliminates chain/no-contact businesses before expensive discovery
  - Rate limiting between businesses reduces burst API usage
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any

from hephae_db.firestore.discovery_jobs import (
    claim_next_pending_job,
    complete_job,
    update_job_progress,
    STATUS_COMPLETED,
    STATUS_FAILED,
)
from hephae_db.firestore.businesses import get_business
from hephae_common.firebase import get_db

from hephae_api.workflows.scheduled_discovery.config import DiscoveryJobConfig
from hephae_api.workflows.scheduled_discovery.quality_gate import run_quality_gate
from hephae_api.workflows.scheduled_discovery.notifier import send_job_completion_email

logger = logging.getLogger(__name__)


async def _is_discovery_fresh(biz_id: str, freshness_days: int) -> bool:
    """Return True if the business was discovered within the freshness window."""
    biz = await get_business(biz_id)
    if not biz:
        return False

    status = biz.get("discoveryStatus", "")
    if status not in ("discovered", "analyzed"):
        return False

    # Check discoveredAt timestamp
    discovered_at = biz.get("discoveredAt") or biz.get("updatedAt")
    if not discovered_at:
        return False

    if hasattr(discovered_at, "seconds"):
        discovered_at = datetime.utcfromtimestamp(discovered_at.seconds)

    if isinstance(discovered_at, str):
        try:
            discovered_at = datetime.fromisoformat(discovered_at)
        except ValueError:
            return False

    cutoff = datetime.utcnow() - timedelta(days=freshness_days)
    return discovered_at > cutoff


async def _run_discovery_for_business(biz_id: str, biz_name: str) -> dict | None:
    """Run the discovery pipeline on a business. Returns enriched identity or None."""
    logger.info(f"[Orchestrator] Running discovery: {biz_name} ({biz_id})")
    try:
        from hephae_api.workflows.enrichment_utils import enrich_business_profile
        from hephae_api.workflows.analysis_utils import PROMOTE_KEYS

        biz = await get_business(biz_id)
        if not biz:
            return None

        enriched = await enrich_business_profile(
            biz.get("name", biz_name),
            biz.get("address", ""),
            biz_id,
        )

        if enriched:
            db = get_db()
            top_level = {k: enriched[k] for k in PROMOTE_KEYS if k in enriched}
            await asyncio.to_thread(
                db.collection("businesses").document(biz_id).update,
                {
                    **top_level,
                    "identity": {**enriched, "docId": biz_id},
                    "discoveryStatus": "discovered",
                    "discoveredAt": datetime.utcnow(),
                },
            )
            return {**enriched, "docId": biz_id}

        return None
    except Exception as e:
        logger.error(f"[Orchestrator] Discovery failed for {biz_id}: {e}")
        return None


async def _process_business(
    biz_id: str,
    biz_name: str,
    job_id: str,
    config: DiscoveryJobConfig,
    skip_reasons: list[str],
) -> str:
    """Process a single business through discovery → quality gate.

    Returns: "qualified" | "skipped:<reason>" | "failed"
    """
    settings = config.settings

    # --- Freshness check (discovery) ---
    if await _is_discovery_fresh(biz_id, settings.freshnessDiscoveryDays):
        reason = f"Discovery fresh: {biz_name}"
        logger.info(f"[Orchestrator] Skipping (fresh discovery): {biz_id}")
        skip_reasons.append(f"Already discovered recently: {biz_name}")
        return "skipped:fresh_discovery"

    # --- Discovery pipeline ---
    identity = await _run_discovery_for_business(biz_id, biz_name)
    if not identity:
        skip_reasons.append(f"Discovery failed: {biz_name}")
        return "failed"

    # --- Quality gate ---
    gate_result = await run_quality_gate(identity)
    if not gate_result.get("qualified"):
        reason = gate_result.get("reason", "Quality gate failed")
        logger.info(f"[Orchestrator] Disqualified: {biz_name} — {reason}")
        skip_reasons.append(f"{biz_name}: {reason}")
        await update_job_progress(job_id, increment={"skipped": 1}, skip_reason=f"{biz_name}: {reason}")
        return f"skipped:{reason}"

    logger.info(f"[Orchestrator] Qualified: {biz_name} — {gate_result.get('reason', '')}")
    await update_job_progress(job_id, increment={"qualified": 1})

    return "qualified"


async def _process_zip(
    job_id: str,
    target: Any,
    config: DiscoveryJobConfig,
    skip_reasons: list[str],
) -> tuple[int, int, int]:
    """Scan a zip code and process each business. Returns (total, qualified, failed)."""
    from hephae_agents.discovery.zipcode_scanner import scan_zipcode

    zip_code = target.zipCode
    business_types = target.businessTypes
    settings = config.settings

    logger.info(f"[Orchestrator] Scanning zip {zip_code}, types={business_types}")

    try:
        businesses = await scan_zipcode(zip_code, force=False)
    except Exception as e:
        logger.error(f"[Orchestrator] scan_zipcode failed for {zip_code}: {e}")
        await update_job_progress(job_id, completed_zip=True)
        return 0, 0, 0

    # Filter by business type if specified
    if business_types:
        type_set = {t.lower() for t in business_types}
        businesses = [
            b for b in businesses
            if any(t in (b.category or "").lower() for t in type_set)
            or any(t in (b.businessType or "").lower() for t in type_set)
        ] or businesses  # fall back to all if filter removes everything

    total = len(businesses)
    qualified = 0
    failed = 0

    await update_job_progress(job_id, increment={"totalBusinesses": total})

    for biz in businesses:
        biz_id = getattr(biz, "id", None) or getattr(biz, "slug", None)
        biz_name = getattr(biz, "name", str(biz))

        if not biz_id:
            logger.warning(f"[Orchestrator] Business has no ID, skipping: {biz_name}")
            failed += 1
            continue

        outcome = await _process_business(biz_id, biz_name, job_id, config, skip_reasons)

        if outcome == "qualified":
            qualified += 1
        elif outcome == "failed":
            failed += 1
            await update_job_progress(job_id, increment={"failed": 1})

        # Rate limiting — prevent burst API usage
        await asyncio.sleep(settings.rateLimitSeconds)

    await update_job_progress(job_id, completed_zip=True)
    return total, qualified, failed


async def run_next_pending_job() -> bool:
    """Claim and run the next pending discovery job.

    Returns True if a job was found and processed, False if no pending jobs.
    Called by the Cloud Run Job entrypoint on each execution.
    """
    job = await claim_next_pending_job()
    if not job:
        logger.info("[Orchestrator] No pending discovery jobs found.")
        return False

    job_id = job["id"]
    logger.info(f"[Orchestrator] Starting job {job_id}: {job.get('name')}")

    config = DiscoveryJobConfig.from_firestore(job)
    skip_reasons: list[str] = []

    # Spin up ephemeral crawl4ai for this job
    ephemeral_name = f"marketing-{job_id[:8]}"
    crawl4ai_url: str | None = None
    try:
        from infra.crawl4ai.ephemeral import create_ephemeral_crawl4ai, destroy_ephemeral_crawl4ai

        crawl4ai_url = await create_ephemeral_crawl4ai(ephemeral_name)
        if crawl4ai_url:
            os.environ["CRAWL4AI_URL"] = crawl4ai_url
            logger.info(f"[Orchestrator] Ephemeral crawl4ai ready: {crawl4ai_url}")
    except Exception as e:
        logger.warning(f"[Orchestrator] Failed to create ephemeral crawl4ai: {e}")

    try:
        for target in config.targets:
            total, qualified, failed = await _process_zip(
                job_id, target, config, skip_reasons
            )
            logger.info(
                f"[Orchestrator] Zip {target.zipCode} done: "
                f"total={total}, qualified={qualified}, failed={failed}"
            )

        await complete_job(job_id, STATUS_COMPLETED)

        # Reload progress for email
        from hephae_db.firestore.discovery_jobs import get_discovery_job
        final_job = await get_discovery_job(job_id) or job
        progress = final_job.get("progress", {})

        await send_job_completion_email(final_job, progress, skip_reasons[:20])

    except Exception as e:
        logger.exception(f"[Orchestrator] Job {job_id} failed: {e}")
        await complete_job(job_id, STATUS_FAILED, error=str(e))
        # Still notify on failure
        from hephae_db.firestore.discovery_jobs import get_discovery_job
        final_job = await get_discovery_job(job_id) or job
        final_job["status"] = STATUS_FAILED
        await send_job_completion_email(final_job, final_job.get("progress", {}), skip_reasons[:20])

    finally:
        # Tear down ephemeral crawl4ai
        if crawl4ai_url:
            try:
                await destroy_ephemeral_crawl4ai(ephemeral_name)
                logger.info(f"[Orchestrator] Ephemeral crawl4ai destroyed: {ephemeral_name}")
            except Exception as e:
                logger.warning(f"[Orchestrator] Failed to destroy ephemeral crawl4ai: {e}")

    return True
