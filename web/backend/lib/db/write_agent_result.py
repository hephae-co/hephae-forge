"""
writeAgentResult — single write path for all analysis agent outputs.

Writes to two destinations:
  1. Firestore businesses/{slug}.latestOutputs.{agentName} — current state for fast app reads
  2. BigQuery hephae.analyses — permanent append-only history

BQ write is fire-and-forget. Failures are logged but never block the API response.

RULE: raw_data must never contain binary blobs (base64 images, HTML).
      Strip menuScreenshotBase64 and any Buffer before calling this function.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from google.cloud.firestore_v1 import SERVER_TIMESTAMP

logger = logging.getLogger(__name__)


class AgentResultOptions:
    def __init__(
        self,
        business_slug: str,
        business_name: str,
        agent_name: str,
        agent_version: str,
        triggered_by: str,  # 'user' | 'weekly_job' | 'api_v1'
        raw_data: Any,
        zip_code: Optional[str] = None,
        score: Optional[float] = None,
        summary: Optional[str] = None,
        report_url: Optional[str] = None,
        kpis: Optional[dict[str, Any]] = None,
    ):
        self.business_slug = business_slug
        self.business_name = business_name
        self.agent_name = agent_name
        self.agent_version = agent_version
        self.triggered_by = triggered_by
        self.raw_data = raw_data
        self.zip_code = zip_code
        self.score = score
        self.summary = summary
        self.report_url = report_url
        self.kpis = kpis


def _extract_promoted_kpis(agent_name: str, raw_data: Any) -> dict[str, Any]:
    """Extract type-specific promoted BQ columns from rawData."""
    if not raw_data or not isinstance(raw_data, dict):
        return {}

    d = raw_data

    if agent_name == "margin_surgeon":
        result: dict[str, Any] = {}
        if isinstance(d.get("total_leakage"), (int, float)):
            result["total_leakage"] = d["total_leakage"]
        if isinstance(d.get("menu_items"), list):
            result["menu_item_count"] = len(d["menu_items"])
        return result

    if agent_name == "seo_auditor":
        sections = d.get("sections", [])
        if not isinstance(sections, list):
            return {}
        result = {}
        for s in sections:
            if not isinstance(s, dict):
                continue
            sid = s.get("id")
            score = s.get("score")
            if sid == "technical":
                result["seo_technical_score"] = score
            elif sid == "content":
                result["seo_content_score"] = score
            elif sid == "ux":
                result["seo_ux_score"] = score
            elif sid == "performance":
                result["seo_performance_score"] = score
            elif sid == "authority":
                result["seo_authority_score"] = score
        return result

    if agent_name == "traffic_forecaster":
        forecast = d.get("forecast", [])
        if not isinstance(forecast, list):
            return {}
        slots = []
        for day in forecast:
            if isinstance(day, dict) and isinstance(day.get("slots"), list):
                slots.extend(day["slots"])
        if slots:
            scores = [s.get("score", 0) for s in slots if isinstance(s, dict)]
            if scores:
                return {"peak_slot_score": max(scores)}
        return {}

    if agent_name == "competitive_analyzer":
        analysis = d.get("competitor_analysis", [])
        if not isinstance(analysis, list):
            return {}
        result = {"competitor_count": len(analysis)}
        if analysis:
            threats = [c.get("threat_level", 0) for c in analysis if isinstance(c, dict)]
            if threats:
                result["avg_threat_level"] = sum(threats) / len(threats)
        return result

    return {}


async def write_agent_result(
    business_slug: str = "",
    business_name: str = "",
    agent_name: str = "",
    agent_version: str = "",
    triggered_by: str = "user",
    raw_data: Any = None,
    zip_code: Optional[str] = None,
    score: Optional[float] = None,
    summary: Optional[str] = None,
    report_url: Optional[str] = None,
    kpis: Optional[dict[str, Any]] = None,
    opts: Optional[AgentResultOptions] = None,
) -> None:
    """Write analysis agent output to Firestore + BigQuery.

    Accepts either keyword arguments directly or a single AgentResultOptions via opts=.
    """
    if opts is None:
        opts = AgentResultOptions(
            business_slug=business_slug,
            business_name=business_name,
            agent_name=agent_name,
            agent_version=agent_version,
            triggered_by=triggered_by,
            raw_data=raw_data,
            zip_code=zip_code,
            score=score,
            summary=summary,
            report_url=report_url,
            kpis=kpis,
        )
    from backend.lib.firebase import db
    from backend.lib.bigquery import bq_insert

    run_at = datetime.now(timezone.utc)
    analysis_id = f"{opts.agent_name}-{int(run_at.timestamp() * 1000)}"

    # --- 1. Firestore upsert (current state) ---
    # Use update() so dotted paths like latestOutputs.seo_auditor are treated as nested fields,
    # not literal top-level keys with dots. Fall back to set() if the document doesn't exist yet.
    latest_output_entry = {
        "score": opts.score,
        "summary": opts.summary,
        "reportUrl": opts.report_url,
        "agentVersion": opts.agent_version,
        "runAt": run_at,
        **(opts.kpis or {}),
    }

    update_payload: dict[str, Any] = {
        "updatedAt": run_at,
        f"latestOutputs.{opts.agent_name}": latest_output_entry,
    }
    if opts.zip_code:
        update_payload["zipCode"] = opts.zip_code

    try:
        db.document(f"businesses/{opts.business_slug}").update(update_payload)
    except Exception as err:
        # gRPC NOT_FOUND code = 5
        if hasattr(err, "code") and callable(err.code) and err.code().value[0] == 5:
            try:
                db.document(f"businesses/{opts.business_slug}").set({
                    "updatedAt": run_at,
                    **({"zipCode": opts.zip_code} if opts.zip_code else {}),
                    "latestOutputs": {opts.agent_name: latest_output_entry},
                })
            except Exception as set_err:
                logger.error(
                    f"[DB] Firestore set failed for {opts.business_slug}/{opts.agent_name}: {set_err}"
                )
        else:
            logger.error(
                f"[DB] Firestore update failed for {opts.business_slug}/{opts.agent_name}: {err}"
            )

    # --- 2. BigQuery append (permanent history) — fire and forget ---
    promoted = _extract_promoted_kpis(opts.agent_name, opts.raw_data)

    row = {
        "analysis_id": analysis_id,
        "business_slug": opts.business_slug,
        "business_name": opts.business_name,
        "zip_code": opts.zip_code,
        "agent_name": opts.agent_name,
        "agent_version": opts.agent_version,
        "run_at": run_at,
        "triggered_by": opts.triggered_by,
        "score": opts.score,
        "summary": opts.summary,
        "report_url": opts.report_url,
        # Promoted KPI columns
        "total_leakage": promoted.get("total_leakage"),
        "menu_item_count": promoted.get("menu_item_count"),
        "seo_technical_score": promoted.get("seo_technical_score"),
        "seo_content_score": promoted.get("seo_content_score"),
        "seo_ux_score": promoted.get("seo_ux_score"),
        "seo_performance_score": promoted.get("seo_performance_score"),
        "seo_authority_score": promoted.get("seo_authority_score"),
        "peak_slot_score": promoted.get("peak_slot_score"),
        "competitor_count": promoted.get("competitor_count"),
        "avg_threat_level": promoted.get("avg_threat_level"),
        # Full output — blobs must be stripped by caller
        "raw_data": json.dumps(opts.raw_data) if opts.raw_data is not None else None,
    }

    asyncio.get_event_loop().run_in_executor(
        None,
        lambda: _bq_insert_sync(bq_insert, "analyses", row, analysis_id),
    )


def _bq_insert_sync(bq_insert_fn, table: str, row: dict, analysis_id: str) -> None:
    """Synchronous wrapper for fire-and-forget BQ insert."""
    import asyncio

    try:
        asyncio.run(bq_insert_fn(table, row))
    except Exception as err:
        logger.error(f"[DB] BQ analyses write failed for {analysis_id}: {err}")
