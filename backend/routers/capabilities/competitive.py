"""POST /api/capabilities/competitive — Competitive analysis capability."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.agents.competitive_analysis import (
    competitor_profiler_agent,
    market_positioning_agent,
)
from backend.agents.marketing_swarm import generate_and_draft_marketing_content
from backend.lib.report_storage import generate_slug, upload_report
from backend.lib.report_templates import build_competitive_report
from backend.lib.db import write_agent_result, enrich_identity
from backend.config import AgentVersions
from backend.lib.adk_helpers import user_msg

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/capabilities/competitive")
async def capabilities_competitive(request: Request):
    try:
        body = await request.json()
        identity = enrich_identity(body.get("identity", {}))

        if not identity or not identity.get("competitors") or len(identity["competitors"]) == 0:
            return JSONResponse(
                {"error": "Missing competitors array. Please run discovery first."},
                status_code=400,
            )

        session_service = InMemorySessionService()
        runner = Runner(
            app_name="competitive-analysis",
            agent=competitor_profiler_agent,
            session_service=session_service,
        )
        session_id = f"comp-{int(time.time() * 1000)}"
        user_id = "sys"

        await session_service.create_session(
            app_name="competitive-analysis", user_id=user_id, session_id=session_id, state={}
        )

        # Step 1: Profile Competitors
        logger.info("[API/Competitive] Step 1: Profiling Competitors...")
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
                    if getattr(part, "thought", False):
                        continue
                    if getattr(part, "text", None):
                        competitor_brief += part.text

        # Step 2: Market Positioning
        logger.info("[API/Competitive] Step 2: Running Market Strategy...")
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
                    if getattr(part, "thought", False):
                        continue
                    if getattr(part, "text", None):
                        strategy_buffer += part.text

        # Robust JSON extraction
        clean_json_str = re.sub(r"```json\s*", "", strategy_buffer)
        clean_json_str = re.sub(r"```\s*", "", clean_json_str).strip()
        fb = clean_json_str.find("{")
        lb = clean_json_str.rfind("}")
        if fb != -1 and lb > fb:
            clean_json_str = clean_json_str[fb : lb + 1]
        payload = json.loads(clean_json_str)

        logger.info(f"[API/Competitive] Success: {list(payload.keys())}")

        # Fire and forget marketing generation
        asyncio.create_task(
            generate_and_draft_marketing_content(
                {"identity": identity, "competitive": payload}, "Competitive Strategy"
            )
        )

        slug = generate_slug(identity.get("name", "unknown"))

        report_url = await upload_report(
            slug=slug,
            report_type="competitive",
            html_content=build_competitive_report(payload, identity),
            identity=identity,
            summary=payload.get("market_summary", "Competitive analysis complete"),
        )

        asyncio.create_task(
            write_agent_result(
                business_slug=slug,
                business_name=identity.get("name", "unknown"),
                agent_name="competitive_analyzer",
                agent_version=AgentVersions.COMPETITIVE_ANALYZER,
                triggered_by="user",
                summary=payload.get("market_summary", "Competitive analysis complete"),
                report_url=report_url or None,
                raw_data=payload,
            )
        )

        result = {**payload}
        if report_url:
            result["reportUrl"] = report_url

        return JSONResponse(result)

    except Exception as exc:
        logger.error(f"[API/Competitive] Failed: {exc}")
        return JSONResponse(
            {"error": str(exc) or "Failed to analyze competitors."},
            status_code=500,
        )
