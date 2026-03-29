"""BigQuery persistence for AI tool discovery.

Two tables (append-only, no Firestore mirror):

  hephae.ai_tools      — One row per tool × vertical × week. Denormalized.
  hephae.ai_tool_runs  — One row per discovery run (metadata + weekly highlight).

Popularity and first-seen are derived at query time:
  - first_seen:  MIN(assessed_week) WHERE tool_id = x
  - popularity:  COUNT(DISTINCT assessed_week) WHERE tool_id = x AND vertical = y

DDL (run once per environment — see create_tables_ddl()):
  bq query --use_legacy_sql=false "$(python -c 'from hephae_db.bigquery.ai_tools import create_tables_ddl; print(create_tables_ddl())')"
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from datetime import datetime
from typing import Any

from google.cloud import bigquery

from hephae_db.bigquery.writer import bq_insert

logger = logging.getLogger(__name__)

_PROJECT_ID = (
    os.getenv("BIGQUERY_PROJECT_ID")
    or os.getenv("GCP_PROJECT_ID")
    or os.getenv("GOOGLE_CLOUD_PROJECT", "")
)
DATASET = "hephae"
TABLE_TOOLS = "ai_tools"
TABLE_RUNS = "ai_tool_runs"

_client: bigquery.Client | None = None


def _get_client() -> bigquery.Client:
    global _client
    if _client is None:
        _client = bigquery.Client(project=_PROJECT_ID)
    return _client


def make_tool_id(tool_name: str, vendor: str) -> str:
    """Stable 12-char ID derived from tool name + vendor (SHA-1 prefix)."""
    raw = f"{tool_name.lower().strip()}|{vendor.lower().strip()}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def create_tables_ddl() -> str:
    """Return DDL to create both AI tools tables (CREATE TABLE IF NOT EXISTS).

    Run once per environment:
        bq query --use_legacy_sql=false '<DDL>'
    """
    project = _PROJECT_ID
    return f"""
CREATE TABLE IF NOT EXISTS `{project}.{DATASET}.{TABLE_TOOLS}` (
  tool_id              STRING    NOT NULL,
  tool_name            STRING    NOT NULL,
  vendor               STRING,
  technology_category  STRING,
  url                  STRING,
  description          STRING,
  pricing              STRING,
  is_free              BOOL,
  free_alternative_to  STRING,
  ai_capability        STRING,
  reputation_tier      STRING,
  source_url           STRING,
  vertical             STRING    NOT NULL,
  relevance_score      STRING,
  category             STRING,
  action_for_owner     STRING,
  assessed_week        STRING    NOT NULL,
  assessed_at          TIMESTAMP NOT NULL,
  is_test              BOOL
);

CREATE TABLE IF NOT EXISTS `{project}.{DATASET}.{TABLE_RUNS}` (
  run_id                 STRING    NOT NULL,
  vertical               STRING    NOT NULL,
  week_of                STRING    NOT NULL,
  total_tools            INT64,
  new_tools_count        INT64,
  high_relevance_count   INT64,
  highlight_tool_name    STRING,
  highlight_title        STRING,
  highlight_detail       STRING,
  highlight_action       STRING,
  generated_at           TIMESTAMP NOT NULL,
  is_test                BOOL
);
""".strip()


async def _run_query(
    query: str,
    params: list[bigquery.ScalarQueryParameter] | None = None,
) -> list[dict[str, Any]]:
    """Execute a parameterized BQ SELECT in a thread."""
    client = _get_client()
    job_config = bigquery.QueryJobConfig(query_parameters=params or [])

    def _execute() -> list[dict[str, Any]]:
        job = client.query(query, job_config=job_config)
        return [dict(row) for row in job.result()]

    return await asyncio.to_thread(_execute)


async def _get_existing_tool_ids(vertical: str, week_of: str) -> set[str]:
    """Return tool_ids that have appeared for this vertical BEFORE week_of."""
    project = _PROJECT_ID
    query = f"""
        SELECT DISTINCT tool_id
        FROM `{project}.{DATASET}.{TABLE_TOOLS}`
        WHERE vertical = @vertical
          AND assessed_week < @week_of
          AND is_test IS NOT TRUE
    """
    params = [
        bigquery.ScalarQueryParameter("vertical", "STRING", vertical),
        bigquery.ScalarQueryParameter("week_of", "STRING", week_of),
    ]
    try:
        rows = await _run_query(query, params)
        return {r["tool_id"] for r in rows}
    except Exception as e:
        logger.warning(f"[AiTools] Could not fetch existing tool IDs: {e}")
        return set()


async def save_ai_tool_run(
    vertical: str,
    week_of: str,
    tools: list[dict[str, Any]],
    weekly_highlight: dict[str, str],
    test_mode: bool = False,
) -> str:
    """Persist a discovery run to BQ. Returns run_id (vertical-week_of).

    Inserts one row per tool into ai_tools and one row into ai_tool_runs.
    All inserts are fire-and-forget — failures are logged but never raised.
    """
    now = datetime.utcnow()
    run_id = f"{vertical}-{week_of}"

    # Determine which tools are newly seen this week
    existing_ids = await _get_existing_tool_ids(vertical, week_of)

    new_count = 0
    high_count = 0

    # Collect (tool, tool_id, is_new) for Firestore upsert after BQ writes
    tool_meta: list[tuple[dict[str, Any], str, bool]] = []

    for tool in tools:
        tool_name = tool.get("toolName", "")
        vendor = tool.get("vendor", "")
        tool_id = make_tool_id(tool_name, vendor)
        is_new = tool_id not in existing_ids
        if is_new:
            new_count += 1
        if tool.get("relevanceScore") == "HIGH":
            high_count += 1

        row: dict[str, Any] = {
            "tool_id": tool_id,
            "tool_name": tool_name,
            "vendor": vendor,
            "technology_category": tool.get("technologyCategory", "Standalone SaaS"),
            "url": tool.get("url"),
            "description": tool.get("description"),
            "pricing": tool.get("pricing"),
            "is_free": bool(tool.get("isFree", False)),
            "free_alternative_to": tool.get("freeAlternativeTo"),
            "ai_capability": tool.get("aiCapability"),
            "reputation_tier": tool.get("reputationTier"),
            "source_url": tool.get("sourceUrl"),
            "vertical": vertical,
            "relevance_score": tool.get("relevanceScore", "MEDIUM"),
            "category": tool.get("category"),
            "action_for_owner": tool.get("actionForOwner"),
            "assessed_week": week_of,
            "assessed_at": now,
            "is_test": test_mode,
        }
        try:
            await bq_insert(TABLE_TOOLS, row)
        except Exception as e:
            logger.warning(f"[AiTools] Failed to insert tool {tool_id} ({tool_name}): {e}")

        tool_meta.append((tool, tool_id, is_new))

    highlight = weekly_highlight or {}
    run_row: dict[str, Any] = {
        "run_id": run_id,
        "vertical": vertical,
        "week_of": week_of,
        "total_tools": len(tools),
        "new_tools_count": new_count,
        "high_relevance_count": high_count,
        "highlight_tool_name": highlight.get("toolName") or highlight.get("tool_name"),
        "highlight_title": highlight.get("title"),
        "highlight_detail": highlight.get("detail"),
        "highlight_action": highlight.get("action"),
        "generated_at": now,
        "is_test": test_mode,
    }
    try:
        await bq_insert(TABLE_RUNS, run_row)
    except Exception as e:
        logger.warning(f"[AiTools] Failed to insert run {run_id}: {e}")

    # Fire-and-forget Firestore upserts — serving layer for chat UI / blog writer
    # Runs concurrently after BQ writes complete; failures are logged but never raised
    if not test_mode and tool_meta:
        from hephae_db.firestore.ai_tools import upsert_tool as _fs_upsert

        async def _sync_to_firestore() -> None:
            await asyncio.gather(
                *[
                    _fs_upsert(
                        tool_id=tid,
                        tool=t,
                        vertical=vertical,
                        week_of=week_of,
                        is_new=new,
                    )
                    for t, tid, new in tool_meta
                ],
                return_exceptions=True,
            )

        asyncio.ensure_future(_sync_to_firestore())

    logger.info(
        f"[AiTools] Saved {run_id}: {len(tools)} tools, "
        f"{new_count} new, {high_count} high relevance"
    )
    return run_id


async def get_ai_tool_run(
    vertical: str,
    week_of: str,
    include_test: bool = False,
) -> dict[str, Any] | None:
    """Get a specific run (run metadata + all tools)."""
    project = _PROJECT_ID
    test_filter = "" if include_test else "AND (t.is_test IS NOT TRUE)"

    tools_query = f"""
        SELECT *
        FROM `{project}.{DATASET}.{TABLE_TOOLS}` t
        WHERE t.vertical = @vertical
          AND t.assessed_week = @week_of
          {test_filter}
        ORDER BY t.relevance_score DESC, t.tool_name ASC
    """
    run_query = f"""
        SELECT *
        FROM `{project}.{DATASET}.{TABLE_RUNS}`
        WHERE vertical = @vertical
          AND week_of = @week_of
        LIMIT 1
    """
    params = [
        bigquery.ScalarQueryParameter("vertical", "STRING", vertical),
        bigquery.ScalarQueryParameter("week_of", "STRING", week_of),
    ]

    tools_rows, run_rows = await asyncio.gather(
        _run_query(tools_query, params),
        _run_query(run_query, params),
    )

    if not tools_rows and not run_rows:
        return None

    run_meta = run_rows[0] if run_rows else {}
    tools = [_serialize_tool_row(r) for r in tools_rows]

    return {
        "id": f"{vertical}-{week_of}",
        "vertical": vertical,
        "weekOf": week_of,
        "tools": tools,
        "totalToolsFound": run_meta.get("total_tools", len(tools)),
        "newToolsCount": run_meta.get("new_tools_count", 0),
        "highRelevanceCount": run_meta.get("high_relevance_count", 0),
        "weeklyHighlight": _extract_highlight(run_meta),
        "generatedAt": _fmt_ts(run_meta.get("generated_at")),
        "testMode": bool(run_meta.get("is_test", False)),
    }


async def get_latest_ai_tool_run(
    vertical: str,
    include_test: bool = False,
) -> dict[str, Any] | None:
    """Get the most recent run for a vertical."""
    project = _PROJECT_ID
    test_filter = "" if include_test else "AND (is_test IS NOT TRUE)"
    query = f"""
        SELECT week_of
        FROM `{project}.{DATASET}.{TABLE_RUNS}`
        WHERE vertical = @vertical
          {test_filter}
        ORDER BY week_of DESC
        LIMIT 1
    """
    params = [bigquery.ScalarQueryParameter("vertical", "STRING", vertical)]
    rows = await _run_query(query, params)
    if not rows:
        return None
    return await get_ai_tool_run(vertical, rows[0]["week_of"], include_test=include_test)


async def list_ai_tool_runs(
    vertical: str | None = None,
    limit: int = 20,
    include_test: bool = False,
) -> list[dict[str, Any]]:
    """List recent run summaries (no tools array — fast query)."""
    project = _PROJECT_ID
    test_filter = "" if include_test else "AND (is_test IS NOT TRUE)"
    vertical_filter = "AND vertical = @vertical" if vertical else ""

    query = f"""
        SELECT
          run_id,
          vertical,
          week_of,
          total_tools,
          new_tools_count,
          high_relevance_count,
          highlight_tool_name,
          highlight_title,
          highlight_detail,
          highlight_action,
          generated_at,
          is_test
        FROM `{project}.{DATASET}.{TABLE_RUNS}`
        WHERE 1=1
          {test_filter}
          {vertical_filter}
        ORDER BY week_of DESC, vertical ASC
        LIMIT @limit
    """
    params = [bigquery.ScalarQueryParameter("limit", "INT64", limit)]
    if vertical:
        params.append(bigquery.ScalarQueryParameter("vertical", "STRING", vertical))

    rows = await _run_query(query, params)
    return [
        {
            "id": r["run_id"],
            "vertical": r["vertical"],
            "weekOf": r["week_of"],
            "totalToolsFound": r.get("total_tools", 0),
            "newToolsCount": r.get("new_tools_count", 0),
            "highRelevanceCount": r.get("high_relevance_count", 0),
            "weeklyHighlight": _extract_highlight(r),
            "generatedAt": _fmt_ts(r.get("generated_at")),
            "testMode": bool(r.get("is_test", False)),
        }
        for r in rows
    ]


async def delete_ai_tool_run(run_id: str) -> None:
    """Delete all rows for a run (vertical-week_of) from both tables."""
    parts = run_id.rsplit("-", 2)
    if len(parts) < 3:
        logger.warning(f"[AiTools] Cannot parse run_id: {run_id}")
        return

    # run_id format: "{vertical}-{year}-W{week}" e.g. "restaurant-2026-W13"
    # Split on last two dashes to get vertical
    week_of = "-".join(parts[-2:])   # "2026-W13"
    vertical = "-".join(parts[:-2])  # "restaurant" (handles underscores + hyphens)

    project = _PROJECT_ID
    client = _get_client()

    def _delete():
        for table, col, val in [
            (TABLE_TOOLS, "assessed_week", week_of),
            (TABLE_RUNS, "week_of", week_of),
        ]:
            dml = f"""
                DELETE FROM `{project}.{DATASET}.{table}`
                WHERE vertical = '{vertical}' AND {col} = '{week_of}'
            """
            client.query(dml).result()

    try:
        await asyncio.to_thread(_delete)
        logger.info(f"[AiTools] Deleted run {run_id}")
    except Exception as e:
        logger.warning(f"[AiTools] Failed to delete run {run_id}: {e}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_tool_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "toolId": row.get("tool_id", ""),
        "toolName": row.get("tool_name", ""),
        "vendor": row.get("vendor", ""),
        "technologyCategory": row.get("technology_category", ""),
        "url": row.get("url", ""),
        "description": row.get("description", ""),
        "pricing": row.get("pricing", ""),
        "isFree": bool(row.get("is_free", False)),
        "freeAlternativeTo": row.get("free_alternative_to"),
        "aiCapability": row.get("ai_capability", ""),
        "reputationTier": row.get("reputation_tier", ""),
        "sourceUrl": row.get("source_url", ""),
        "vertical": row.get("vertical", ""),
        "relevanceScore": row.get("relevance_score", ""),
        "category": row.get("category", ""),
        "actionForOwner": row.get("action_for_owner", ""),
        "assessedWeek": row.get("assessed_week", ""),
    }


def _extract_highlight(run_meta: dict[str, Any]) -> dict[str, str]:
    return {
        "toolName": run_meta.get("highlight_tool_name") or "",
        "title": run_meta.get("highlight_title") or "",
        "detail": run_meta.get("highlight_detail") or "",
        "action": run_meta.get("highlight_action") or "",
    }


def _fmt_ts(ts: Any) -> str | None:
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts.isoformat()
    return str(ts)
