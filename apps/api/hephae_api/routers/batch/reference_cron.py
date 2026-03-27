"""Research Reference Harvester cron — weekly external research collection.

GET /api/cron/reference-harvest

Runs Friday 6:00 AM ET (11:00 UTC) — before the weekend blog/outreach cycle.
Harvests authoritative external research (Deloitte, NRA, USDA, govt agencies,
trade press) on topics relevant to Hephae: restaurant margins, food costs,
commodity prices, small business profitability, restaurant tech, labor costs.

Stores clean structured references in Firestore `research_references` collection
for use by blogs, outreach agents, and pulse synthesis.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException

from hephae_api.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reference-cron"])


@router.get("/api/cron/reference-harvest")
async def reference_harvest_cron(
    authorization: str | None = Header(None),
    x_cron_secret: str | None = Header(None),
):
    """Harvest weekly research references from authoritative external sources.

    Idempotent — skips URLs already stored. Safe to re-run.
    """
    # Auth
    cron_token = x_cron_secret or authorization
    if settings.CRON_SECRET and cron_token != f"Bearer {settings.CRON_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    from hephae_agents.research.reference_harvester import run_weekly_harvest

    logger.info("[ReferenceCron] Starting weekly research harvest")
    result = await run_weekly_harvest()
    logger.info(
        f"[ReferenceCron] Done — {result['harvested']} harvested, "
        f"{result['saved']} saved, topics: {result['by_topic']}"
    )
    return {"success": True, **result}
