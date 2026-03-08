"""POST /api/v1/competitive — V1 Competitive Analysis (no report storage)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from backend.lib.auth import verify_api_key

from hephae_capabilities.competitive_analysis import (
    competitor_profiler_agent,
    market_positioning_agent,
)
from hephae_capabilities.social.marketing_swarm import generate_and_draft_marketing_content
from hephae_common.adk_helpers import user_msg
from backend.types import CompetitiveReport, V1Response

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

        session_service = InMemorySessionService()
        runner = Runner(
            app_name="competitive-analysis",
            agent=competitor_profiler_agent,
            session_service=session_service,
        )
        session_id = f"comp-v1-{int(time.time() * 1000)}"
        user_id = "api-v1-client"

        await session_service.create_session(
            app_name="competitive-analysis", user_id=user_id, session_id=session_id, state={}
        )

        # Step 1: Profile Competitors
        logger.info(f"[V1/Competitive] Step 1: Profiling Competitors for {identity.get('name')}...")
        profiler_prompt = f"Research these competitors: {json.dumps(identity['competitors'])}"

        competitor_brief = ""
        async for raw_event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_msg(profiler_prompt),
        ):
            content = getattr(raw_event, "content", None)
            if content and hasattr(content, "parts"):
                for part in content.parts:
                    if getattr(part, "text", None):
                        competitor_brief += part.text

        # Step 2: Market Positioning
        logger.info("[V1/Competitive] Step 2: Running Market Strategy...")
        positioning_runner = Runner(
            app_name="competitive-analysis",
            agent=market_positioning_agent,
            session_service=session_service,
        )

        strategy_prompt = (
            f"TARGET RESTAURANT: {json.dumps(identity)}\n\n"
            f"COMPETITORS BRIEF:\n{competitor_brief}\n\n"
            "Generate the final competitive json report."
        )

        strategy_buffer = ""
        async for raw_event in positioning_runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_msg(strategy_prompt),
        ):
            content = getattr(raw_event, "content", None)
            if content and hasattr(content, "parts"):
                for part in content.parts:
                    if getattr(part, "text", None):
                        strategy_buffer += part.text

        clean_str = re.sub(r"```json\s*", "", strategy_buffer)
        clean_str = re.sub(r"```\s*", "", clean_str).strip()
        payload = json.loads(clean_str)

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
