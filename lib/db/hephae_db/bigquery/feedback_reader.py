"""Feedback reader — aggregate query functions for the learning cycle.

Reads from hephae.agent_feedback to extract patterns for:
- Approval rate by industry/zip
- Crawl success rate by platform
- Eval score distributions
- Agent run durations
"""

from __future__ import annotations

import logging
import os
from typing import Any

from google.cloud import bigquery

logger = logging.getLogger(__name__)

_PROJECT_ID = os.getenv("BIGQUERY_PROJECT_ID", "")
DATASET = "hephae"
TABLE = "agent_feedback"


def _get_client() -> bigquery.Client:
    return bigquery.Client(project=_PROJECT_ID)


def _run_query(query: str, params: list[bigquery.ScalarQueryParameter] | None = None) -> list[dict[str, Any]]:
    """Execute a parameterized BigQuery query and return rows as dicts."""
    client = _get_client()
    job_config = bigquery.QueryJobConfig(query_parameters=params or [])
    job = client.query(query, job_config=job_config, location="US")
    return [dict(row) for row in job.result()]


async def get_approval_rates_by_industry(
    min_sample_size: int = 5,
    days_back: int = 30,
) -> list[dict[str, Any]]:
    """Approval rates grouped by business_type.

    Returns: [{business_type, total, approved, rejected, approval_rate}]
    """
    import asyncio

    query = f"""
        SELECT
            business_type,
            COUNT(*) AS total,
            COUNTIF(human_decision = 'approve') AS approved,
            COUNTIF(human_decision = 'reject') AS rejected,
            SAFE_DIVIDE(COUNTIF(human_decision = 'approve'), COUNT(*)) AS approval_rate
        FROM `{_PROJECT_ID}.{DATASET}.{TABLE}`
        WHERE human_decision IS NOT NULL
          AND business_type IS NOT NULL
          AND business_type != ''
          AND recorded_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days_back DAY)
        GROUP BY business_type
        HAVING COUNT(*) >= @min_sample
        ORDER BY approval_rate DESC
    """
    params = [
        bigquery.ScalarQueryParameter("days_back", "INT64", days_back),
        bigquery.ScalarQueryParameter("min_sample", "INT64", min_sample_size),
    ]
    return await asyncio.to_thread(_run_query, query, params)


async def get_approval_rates_by_zip(
    min_sample_size: int = 5,
    days_back: int = 30,
) -> list[dict[str, Any]]:
    """Approval rates grouped by zip_code.

    Returns: [{zip_code, total, approved, approval_rate}]
    """
    import asyncio

    query = f"""
        SELECT
            zip_code,
            COUNT(*) AS total,
            COUNTIF(human_decision = 'approve') AS approved,
            SAFE_DIVIDE(COUNTIF(human_decision = 'approve'), COUNT(*)) AS approval_rate
        FROM `{_PROJECT_ID}.{DATASET}.{TABLE}`
        WHERE human_decision IS NOT NULL
          AND zip_code IS NOT NULL
          AND zip_code != ''
          AND recorded_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days_back DAY)
        GROUP BY zip_code
        HAVING COUNT(*) >= @min_sample
        ORDER BY approval_rate DESC
    """
    params = [
        bigquery.ScalarQueryParameter("days_back", "INT64", days_back),
        bigquery.ScalarQueryParameter("min_sample", "INT64", min_sample_size),
    ]
    return await asyncio.to_thread(_run_query, query, params)


async def get_crawl_success_by_platform(
    days_back: int = 30,
) -> list[dict[str, Any]]:
    """Crawl success rates grouped by site_platform and crawl_strategy.

    Returns: [{site_platform, crawl_strategy, total, successes, success_rate, avg_content_length, avg_duration_ms}]
    """
    import asyncio

    query = f"""
        SELECT
            site_platform,
            crawl_strategy,
            COUNT(*) AS total,
            COUNTIF(crawl_success = TRUE) AS successes,
            SAFE_DIVIDE(COUNTIF(crawl_success = TRUE), COUNT(*)) AS success_rate,
            AVG(crawl_content_length) AS avg_content_length,
            AVG(crawl_duration_ms) AS avg_duration_ms
        FROM `{_PROJECT_ID}.{DATASET}.{TABLE}`
        WHERE crawl_strategy IS NOT NULL
          AND site_platform IS NOT NULL
          AND site_platform != ''
          AND recorded_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days_back DAY)
        GROUP BY site_platform, crawl_strategy
        ORDER BY site_platform, success_rate DESC
    """
    params = [
        bigquery.ScalarQueryParameter("days_back", "INT64", days_back),
    ]
    return await asyncio.to_thread(_run_query, query, params)


async def get_eval_score_distribution(
    capability: str | None = None,
    days_back: int = 30,
) -> list[dict[str, Any]]:
    """Eval score distribution, optionally filtered by capability.

    Returns: [{capability, agent_name, avg_score, median_score, min_score, max_score, total, hallucination_rate}]
    """
    import asyncio

    where_clause = ""
    params = [
        bigquery.ScalarQueryParameter("days_back", "INT64", days_back),
    ]
    if capability:
        where_clause = "AND capability = @capability"
        params.append(bigquery.ScalarQueryParameter("capability", "STRING", capability))

    query = f"""
        SELECT
            capability,
            agent_name,
            AVG(eval_score) AS avg_score,
            APPROX_QUANTILES(eval_score, 2)[OFFSET(1)] AS median_score,
            MIN(eval_score) AS min_score,
            MAX(eval_score) AS max_score,
            COUNT(*) AS total,
            SAFE_DIVIDE(COUNTIF(is_hallucinated = TRUE), COUNT(*)) AS hallucination_rate
        FROM `{_PROJECT_ID}.{DATASET}.{TABLE}`
        WHERE eval_score IS NOT NULL
          AND recorded_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days_back DAY)
          {where_clause}
        GROUP BY capability, agent_name
        ORDER BY avg_score DESC
    """
    return await asyncio.to_thread(_run_query, query, params)


async def get_agent_run_durations(
    days_back: int = 30,
) -> list[dict[str, Any]]:
    """Agent run durations grouped by agent_name.

    Returns: [{agent_name, capability, avg_duration_ms, p50_duration_ms, p95_duration_ms, total}]
    """
    import asyncio

    query = f"""
        SELECT
            agent_name,
            capability,
            AVG(run_duration_ms) AS avg_duration_ms,
            APPROX_QUANTILES(run_duration_ms, 100)[OFFSET(50)] AS p50_duration_ms,
            APPROX_QUANTILES(run_duration_ms, 100)[OFFSET(95)] AS p95_duration_ms,
            COUNT(*) AS total
        FROM `{_PROJECT_ID}.{DATASET}.{TABLE}`
        WHERE run_duration_ms IS NOT NULL
          AND run_duration_ms > 0
          AND recorded_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days_back DAY)
        GROUP BY agent_name, capability
        ORDER BY avg_duration_ms DESC
    """
    params = [
        bigquery.ScalarQueryParameter("days_back", "INT64", days_back),
    ]
    return await asyncio.to_thread(_run_query, query, params)


async def get_feedback_summary(days_back: int = 7) -> dict[str, Any]:
    """High-level summary of recent feedback for the learning cycle report.

    Returns: {total_runs, avg_eval_score, hallucination_rate, approval_rate, avg_crawl_success_rate}
    """
    import asyncio

    query = f"""
        SELECT
            COUNT(*) AS total_rows,
            COUNT(DISTINCT business_slug) AS unique_businesses,
            AVG(IF(eval_score IS NOT NULL, eval_score, NULL)) AS avg_eval_score,
            SAFE_DIVIDE(
                COUNTIF(is_hallucinated = TRUE),
                COUNTIF(eval_score IS NOT NULL)
            ) AS hallucination_rate,
            SAFE_DIVIDE(
                COUNTIF(human_decision = 'approve'),
                COUNTIF(human_decision IS NOT NULL)
            ) AS approval_rate,
            SAFE_DIVIDE(
                COUNTIF(crawl_success = TRUE),
                COUNTIF(crawl_strategy IS NOT NULL)
            ) AS crawl_success_rate,
            AVG(IF(run_duration_ms > 0, run_duration_ms, NULL)) AS avg_run_duration_ms
        FROM `{_PROJECT_ID}.{DATASET}.{TABLE}`
        WHERE recorded_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days_back DAY)
    """
    params = [
        bigquery.ScalarQueryParameter("days_back", "INT64", days_back),
    ]
    rows = await asyncio.to_thread(_run_query, query, params)
    return rows[0] if rows else {}
