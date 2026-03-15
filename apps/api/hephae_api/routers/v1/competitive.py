"""POST /api/v1/competitive — V1 Competitive Analysis (no report storage)."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from hephae_api.lib.auth import verify_api_key

from hephae_agents.competitive_analysis.runner import run_competitive_analysis
from hephae_agents.social.marketing_swarm import generate_and_draft_marketing_content
from hephae_api.types import CompetitiveReport, V1Response

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/v1/competitive", response_model=V1Response[CompetitiveReport], dependencies=[Depends(verify_api_key)])
async def v1_competitive(request: Request):
    try:
        body = await request.json()
        identity = body.get("identity", {})

        if not identity or not identity.get("competitors") or len(identity["competitors"]) == 0:
            return JSONResponse(
                {"error": "Missing competitors array. Please run /api/v1/discover first."},
                status_code=400,
            )

        logger.info(f"[V1/Competitive] Running analysis for {identity.get('name')}...")

        payload = await run_competitive_analysis(identity)

        logger.info(f"[V1/Competitive] Success: {list(payload.keys())}")

        # Fire and forget marketing
        asyncio.create_task(
            generate_and_draft_marketing_content(
                {"identity": identity, "competitive": payload}, "Competitive Strategy"
            )
        )

        return JSONResponse({"success": True, "data": payload})

    except Exception as exc:
        logger.error(f"[V1/Competitive] Failed: {exc}")
        return JSONResponse(
            {"error": str(exc) or "Failed to analyze competitors."},
            status_code=500,
        )
