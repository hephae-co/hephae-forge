"""Tech Intelligence cron — generates technology landscape profiles for all registered industries.

GET /api/cron/tech-intelligence — Triggered by Cloud Scheduler Sunday 1 AM ET.
Runs TechScout pipeline for each registered industry in sequence (not parallel,
to avoid Google Search rate limits).
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException

from hephae_api.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tech-intelligence-cron"])


@router.get("/api/cron/tech-intelligence")
async def tech_intelligence_cron(
    authorization: str | None = Header(None),
    x_cron_secret: str | None = Header(None),
):
    """Generate technology intelligence profiles for all registered industries."""
    cron_token = x_cron_secret or authorization
    if settings.CRON_SECRET and cron_token != f"Bearer {settings.CRON_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    from hephae_api.workflows.orchestrators.industries import all_industries
    from hephae_api.workflows.orchestrators.tech_intelligence import generate_tech_intelligence

    industries = all_industries()
    results = []
    failed = 0

    for industry in industries:
        try:
            logger.info(f"[TechIntelCron] Running tech scout for {industry.id}")
            result = await generate_tech_intelligence(industry.id)
            if result.get("error"):
                failed += 1
                results.append({
                    "vertical": industry.id,
                    "status": "failed",
                    "error": result["error"],
                })
            else:
                results.append({
                    "vertical": industry.id,
                    "status": "generated",
                    "aiOpportunities": len(result.get("aiOpportunities", [])),
                    "platforms": len(result.get("platforms", {})),
                    "weeklyHighlight": result.get("weeklyHighlight", {}).get("title", ""),
                })
        except Exception as e:
            logger.error(f"[TechIntelCron] Failed for {industry.id}: {e}")
            failed += 1
            results.append({
                "vertical": industry.id,
                "status": "failed",
                "error": str(e),
            })

    logger.info(f"[TechIntelCron] Complete: {len(results) - failed} succeeded, {failed} failed")
    return {
        "success": True,
        "generated": len(results) - failed,
        "failed": failed,
        "results": results,
    }
