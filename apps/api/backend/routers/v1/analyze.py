"""POST /api/v1/analyze — V1 Margin Surgery (expects enrichedProfile with menuScreenshotBase64)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from backend.lib.auth import verify_api_key

from hephae_capabilities.margin_analyzer import (
    vision_intake_agent,
    benchmarker_agent,
    commodity_watchdog_agent,
    surgeon_agent,
    advisor_agent,
)
from hephae_capabilities.social.marketing_swarm import generate_and_draft_marketing_content
from hephae_common.adk_helpers import user_msg
from backend.types import SurgicalReport, V1Response

logger = logging.getLogger(__name__)

router = APIRouter()


def _clean(text: str) -> str:
    return re.sub(r"```json\s*|\s*```", "", text).strip()


@router.post("/v1/analyze", response_model=V1Response[SurgicalReport], dependencies=[Depends(verify_api_key)])
async def v1_analyze(request: Request):
    try:
        body = await request.json()
        enriched_profile = body.get("identity", {})
        advanced_mode = body.get("advancedMode", False)

        if not enriched_profile or not enriched_profile.get("menuScreenshotBase64"):
            return JSONResponse(
                {"error": "Missing EnrichedProfile or menuScreenshotBase64. Ensure you run discovery first."},
                status_code=400,
            )

        logger.info(f"[V1/Analyze] Triggering Margin Surgery for {enriched_profile.get('name')}...")

        identity = {**enriched_profile}
        identity.setdefault("primaryColor", "#0f172a")
        identity.setdefault("secondaryColor", "#334155")
        identity.setdefault("persona", "Local Business")

        session_service = InMemorySessionService()
        session_id = f"margin-v1-{int(time.time() * 1000)}"
        user_id = "api-v1-client"

        await session_service.create_session(
            app_name="hephae-hub",
            user_id=user_id,
            session_id=session_id,
            state={"advancedMode": advanced_mode},
        )

        # 1. Vision Intake
        logger.info("[V1/Analyze] Step 1: Vision Intake...")
        vision_runner = Runner(app_name="hephae-hub", agent=vision_intake_agent, session_service=session_service)
        menu_items_prompt = ""
        menu_items: list = []

        async for raw_event in vision_runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_msg(json.dumps(identity)),
        ):
            event = raw_event
            content = getattr(event, "content", None)
            if content and hasattr(content, "parts"):
                for part in content.parts:
                    fr = getattr(part, "function_response", None)
                    if fr and getattr(fr, "name", None) == "process_menu_items":
                        menu_items = fr.response

            actions = getattr(event, "actions", None)
            if actions:
                delta = getattr(actions, "state_delta", None) or (actions if isinstance(actions, dict) else {})
                if isinstance(delta, dict) and delta.get("menuItems") and not menu_items:
                    val = delta["menuItems"]
                    menu_items_prompt = val if isinstance(val, str) else json.dumps(val)

        if not menu_items and menu_items_prompt:
            menu_items_prompt = _clean(menu_items_prompt)
            try:
                menu_items = json.loads(menu_items_prompt)
            except (json.JSONDecodeError, ValueError):
                return JSONResponse({"error": "Failed to parse menu items from vision agent."}, status_code=500)
        elif menu_items:
            menu_items_prompt = json.dumps(menu_items)
        else:
            return JSONResponse({"error": "No menu items could be extracted."}, status_code=500)

        benchmark_prompt = ""
        commodity_prompt = ""

        if advanced_mode:
            # 2. Benchmarker
            logger.info("[V1/Analyze] Step 2: Benchmarker (Advanced Mode)...")
            benchmark_runner = Runner(
                app_name="hephae-hub", agent=benchmarker_agent, session_service=session_service
            )
            async for raw_event in benchmark_runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_msg(
                    f"Here are the mapped menu items:\n{menu_items_prompt}\n\n"
                    f"For Target Identity:\n{json.dumps(identity)}"
                ),
            ):
                actions = getattr(raw_event, "actions", None)
                if actions:
                    delta = getattr(actions, "state_delta", None) or (
                        actions if isinstance(actions, dict) else {}
                    )
                    if isinstance(delta, dict) and delta.get("benchmarkData"):
                        val = delta["benchmarkData"]
                        benchmark_prompt = val if isinstance(val, str) else json.dumps(val)
            benchmark_prompt = _clean(benchmark_prompt)

            # 3. Commodity Watchdog
            logger.info("[V1/Analyze] Step 3: Commodity Watchdog (Advanced Mode)...")
            commodity_runner = Runner(
                app_name="hephae-hub", agent=commodity_watchdog_agent, session_service=session_service
            )
            async for raw_event in commodity_runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_msg(f"Here are the parsed menu items:\n{menu_items_prompt}"),
            ):
                actions = getattr(raw_event, "actions", None)
                if actions:
                    delta = getattr(actions, "state_delta", None) or (
                        actions if isinstance(actions, dict) else {}
                    )
                    if isinstance(delta, dict) and delta.get("commodityTrends"):
                        val = delta["commodityTrends"]
                        commodity_prompt = val if isinstance(val, str) else json.dumps(val)
            commodity_prompt = _clean(commodity_prompt)

        else:
            logger.info("[V1/Analyze] Fast Mode: Bypassing Benchmarker and Watchdog LLMs.")
            benchmark_prompt = json.dumps(
                {
                    "competitors": [
                        {
                            "competitor_name": "Local Average (Estimate)",
                            "item_match": item.get("item_name", ""),
                            "price": round((item.get("current_price", 0) or 0) * 1.05, 2),
                            "source_url": "",
                            "distance_miles": 1.0,
                        }
                        for item in menu_items
                    ],
                    "macroeconomic_context": {
                        "analysis_hint": "Standard estimation mode enabled. Assume moderate inflation."
                    },
                }
            )
            commodity_prompt = json.dumps(
                [
                    {
                        "ingredient": "GENERAL",
                        "inflation_rate_12mo": 3.2,
                        "trend_description": "Standard national food-at-home inflation estimate.",
                    }
                ]
            )

        # 4. Surgeon
        logger.info("[V1/Analyze] Step 4: The Surgeon...")
        surgeon_runner = Runner(app_name="hephae-hub", agent=surgeon_agent, session_service=session_service)
        surgeon_prompt = ""
        menu_analysis: list = []

        async for raw_event in surgeon_runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_msg(
                f"Here are the arrays:\nMenuItems: {menu_items_prompt}\n"
                f"Benchmarks: {benchmark_prompt}\nCommodities: {commodity_prompt}"
            ),
        ):
            content = getattr(raw_event, "content", None)
            if content and hasattr(content, "parts"):
                for part in content.parts:
                    fr = getattr(part, "function_response", None)
                    if fr and getattr(fr, "name", None) == "perform_margin_surgery":
                        menu_analysis = fr.response

            actions = getattr(raw_event, "actions", None)
            if actions:
                delta = getattr(actions, "state_delta", None) or (actions if isinstance(actions, dict) else {})
                if isinstance(delta, dict) and delta.get("menuAnalysis") and not menu_analysis:
                    val = delta["menuAnalysis"]
                    surgeon_prompt = val if isinstance(val, str) else json.dumps(val)

        if not menu_analysis and surgeon_prompt:
            surgeon_prompt = _clean(surgeon_prompt)
            try:
                parsed = json.loads(surgeon_prompt)
                if isinstance(parsed, list):
                    menu_analysis = parsed
                elif isinstance(parsed, dict):
                    for key in parsed:
                        if isinstance(parsed[key], list):
                            menu_analysis = parsed[key]
                            break
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning(f"Surgeon parse fail: {exc}")

        # 5. Advisor
        logger.info("[V1/Analyze] Step 5: The Advisor...")
        advisor_runner = Runner(app_name="hephae-hub", agent=advisor_agent, session_service=session_service)
        strategic_advice: list = []

        async for raw_event in advisor_runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_msg(f"Here is the menuAnalysis from the Surgeon:\n{surgeon_prompt}"),
        ):
            actions = getattr(raw_event, "actions", None)
            if actions:
                delta = getattr(actions, "state_delta", None) or (actions if isinstance(actions, dict) else {})
                if isinstance(delta, dict) and delta.get("strategicAdvice"):
                    val = delta["strategicAdvice"]
                    raw_adv = val if isinstance(val, str) else json.dumps(val)
                    try:
                        strategic_advice = json.loads(_clean(raw_adv))
                    except (json.JSONDecodeError, ValueError):
                        pass

        logger.info("[V1/Analyze] ADK Margin Surgery Finished.")

        total_leakage = sum(item.get("price_leakage", 0) for item in menu_analysis)
        total_revenue = sum(item.get("current_price", 0) for item in menu_analysis)
        score = max(0, min(100, round(100 - (total_leakage / (total_revenue or 1) * 20))))

        report = {
            "identity": identity,
            "menu_items": menu_analysis,
            "strategic_advice": strategic_advice,
            "overall_score": score,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Fire and forget marketing
        asyncio.create_task(
            generate_and_draft_marketing_content(
                {"identity": enriched_profile, "analyzer": report}, "Margin Surgeon"
            )
        )

        return JSONResponse({"success": True, "data": report})

    except Exception as exc:
        logger.error(f"[V1/Analyze] Orchestration Failed: {exc}")
        return JSONResponse({"error": "Internal Server Error"}, status_code=500)
