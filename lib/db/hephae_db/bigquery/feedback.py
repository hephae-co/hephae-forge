"""Feedback collection — records structured signals from every agent run into BigQuery.

Table: hephae.agent_feedback
Append-only, queried by the learning cycle for pattern extraction.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from hephae_db.bigquery.writer import bq_insert

logger = logging.getLogger(__name__)

TABLE = "agent_feedback"


async def record_feedback(
    *,
    business_slug: str,
    agent_name: str,
    agent_version: str = "",
    capability: str = "",
    zip_code: str = "",
    business_type: str = "",
    eval_score: float | None = None,
    is_hallucinated: bool | None = None,
    human_decision: str | None = None,
    auto_approved: bool | None = None,
    crawl_strategy: str | None = None,
    crawl_success: bool | None = None,
    crawl_content_length: int | None = None,
    crawl_duration_ms: int | None = None,
    site_platform: str | None = None,
    run_duration_ms: int | None = None,
) -> None:
    """Fire-and-forget write to hephae.agent_feedback BigQuery table.

    Failures are logged but never block the caller.
    """
    now = datetime.utcnow()
    feedback_id = f"{agent_name}-{business_slug}-{int(time.time())}"

    row: dict[str, Any] = {
        "feedback_id": feedback_id,
        "business_slug": business_slug,
        "agent_name": agent_name,
        "agent_version": agent_version,
        "capability": capability,
        "zip_code": zip_code,
        "business_type": business_type,
        "recorded_at": now,
    }

    if eval_score is not None:
        row["eval_score"] = eval_score
    if is_hallucinated is not None:
        row["is_hallucinated"] = is_hallucinated
    if human_decision is not None:
        row["human_decision"] = human_decision
    if auto_approved is not None:
        row["auto_approved"] = auto_approved
    if crawl_strategy is not None:
        row["crawl_strategy"] = crawl_strategy
    if crawl_success is not None:
        row["crawl_success"] = crawl_success
    if crawl_content_length is not None:
        row["crawl_content_length"] = crawl_content_length
    if crawl_duration_ms is not None:
        row["crawl_duration_ms"] = crawl_duration_ms
    if site_platform is not None:
        row["site_platform"] = site_platform
    if run_duration_ms is not None:
        row["run_duration_ms"] = run_duration_ms

    try:
        await bq_insert(TABLE, row)
        logger.debug(f"[Feedback] Recorded {feedback_id}")
    except Exception as e:
        logger.warning(f"[Feedback] Failed to record {feedback_id}: {e}")


async def record_evaluation_feedback(
    *,
    business_slug: str,
    capability: str,
    agent_name: str,
    agent_version: str,
    eval_score: float,
    is_hallucinated: bool,
    zip_code: str = "",
    business_type: str = "",
) -> None:
    """Convenience wrapper for evaluation phase feedback."""
    await record_feedback(
        business_slug=business_slug,
        agent_name=agent_name,
        agent_version=agent_version,
        capability=capability,
        zip_code=zip_code,
        business_type=business_type,
        eval_score=eval_score,
        is_hallucinated=is_hallucinated,
    )


async def record_approval_feedback(
    *,
    business_slug: str,
    human_decision: str,
    auto_approved: bool = False,
    zip_code: str = "",
    business_type: str = "",
) -> None:
    """Convenience wrapper for approval decision feedback."""
    await record_feedback(
        business_slug=business_slug,
        agent_name="approval_gate",
        capability="approval",
        zip_code=zip_code,
        business_type=business_type,
        human_decision=human_decision,
        auto_approved=auto_approved,
    )


async def record_crawl_feedback(
    *,
    business_slug: str,
    url: str,
    crawl_strategy: str,
    crawl_success: bool,
    crawl_content_length: int = 0,
    crawl_duration_ms: int = 0,
    site_platform: str = "",
) -> None:
    """Convenience wrapper for crawl telemetry feedback."""
    await record_feedback(
        business_slug=business_slug,
        agent_name="crawl4ai",
        capability="discovery",
        crawl_strategy=crawl_strategy,
        crawl_success=crawl_success,
        crawl_content_length=crawl_content_length,
        crawl_duration_ms=crawl_duration_ms,
        site_platform=site_platform,
    )


async def record_run_feedback(
    *,
    business_slug: str,
    agent_name: str,
    agent_version: str,
    capability: str,
    run_duration_ms: int,
    zip_code: str = "",
    business_type: str = "",
) -> None:
    """Convenience wrapper for agent run timing feedback."""
    await record_feedback(
        business_slug=business_slug,
        agent_name=agent_name,
        agent_version=agent_version,
        capability=capability,
        run_duration_ms=run_duration_ms,
        zip_code=zip_code,
        business_type=business_type,
    )
