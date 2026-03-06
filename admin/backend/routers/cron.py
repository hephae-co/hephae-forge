"""Cron endpoints — GET /api/cron/run-analysis."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Header, Query

from backend.agents.discovery.zipcode_scanner import scan_zipcode
from backend.agents.outreach.communicator import draft_and_send_outreach
from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cron", tags=["cron"])


@router.get("/run-analysis")
async def cron_run_analysis(
    authorization: str | None = Header(None),
    zip: str = Query("10001"),
):
    if settings.CRON_SECRET and authorization != f"Bearer {settings.CRON_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    logger.info(f"[Cron] Starting Analysis Cycle for Zip Code: {zip}")

    try:
        businesses = await scan_zipcode(zip)

        if not businesses:
            return {"success": True, "message": "No businesses processed."}

        report = []
        batch = businesses[:3]

        for biz in batch:
            outreach_success = False
            try:
                result = await draft_and_send_outreach(biz.docId)
                outreach_success = result.get("success", False)
            except Exception as e:
                logger.error(f"[Cron] Outreach failed for {biz.name}: {e}")

            report.append({
                "business": biz.name,
                "outreachSuccess": outreach_success,
            })

            await asyncio.sleep(2)

        return {"success": True, "report": report}
    except Exception as e:
        logger.error(f"[Cron] Fatal error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
