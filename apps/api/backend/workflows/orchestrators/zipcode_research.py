"""Zip code research orchestrator — full pipeline from search to report."""

from __future__ import annotations

import logging

from backend.workflows.agents.research.zipcode_research import research_zipcode_data
from backend.workflows.agents.research.zipcode_report_composer import compose_zipcode_report
from hephae_db.bigquery.reader import query_google_trends
from hephae_db.firestore.research import get_zipcode_report, save_zipcode_run

logger = logging.getLogger(__name__)


async def research_zip_code(
    zip_code: str,
    force: bool = False,
) -> dict:
    """Main entry point for zip code research. Returns {"report": dict, "runId": str}.

    Pipeline:
    1. Check Firestore cache (skip if force=True)
    2. Run GOOGLE_SEARCH research agent
    3. Query BigQuery Google Trends (non-fatal)
    4. Run report composer agent
    5. Save to Firestore (new run with timestamped ID)
    """
    # 1. Check cache
    if not force:
        cached = await get_zipcode_report(zip_code)
        if cached:
            logger.info(f"[ZipCodeResearch] Returning cached report for {zip_code}")
            raw_report = cached["report"] if isinstance(cached, dict) else cached.report
            report_dict = raw_report.model_dump(mode="json") if hasattr(raw_report, "model_dump") else raw_report
            run_id = await save_zipcode_run(zip_code, report_dict)
            return {"report": report_dict, "runId": run_id}

    logger.info(f"[ZipCodeResearch] Starting research pipeline for {zip_code}{' (forced)' if force else ''}")

    # 2. Run GOOGLE_SEARCH research agent
    result = await research_zipcode_data(zip_code)
    findings = result["findings"]
    dma_name = result["dmaName"]

    if not findings or len(findings) < 100:
        raise ValueError(f"Research agent returned insufficient data for {zip_code}")

    # 3. Query BigQuery Google Trends (non-fatal)
    trends_data = None
    if dma_name:
        logger.info(f'[ZipCodeResearch] Querying Google Trends for DMA: "{dma_name}"')
        trends = await query_google_trends(dma_name)
        trends_data = trends.model_dump(mode="json") if hasattr(trends, "model_dump") else {"topTerms": [], "risingTerms": []}
        logger.info(f"[ZipCodeResearch] Trends: {len(trends_data.get('topTerms', []))} top, {len(trends_data.get('risingTerms', []))} rising")
    else:
        logger.info("[ZipCodeResearch] No DMA name extracted, skipping trends")

    # 4. Run report composer agent
    report = await compose_zipcode_report(zip_code, findings, trends_data)

    # 5. Save to Firestore
    run_id = await save_zipcode_run(zip_code, report)
    logger.info(f"[ZipCodeResearch] Research complete and saved as {run_id}")

    return {"report": report, "runId": run_id}
