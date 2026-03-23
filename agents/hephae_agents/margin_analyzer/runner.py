"""Margin Analyzer runner — stateless 5-stage pipeline.

Stage 1: Vision Intake — extract menu items from screenshot
Stage 2+3: Benchmarker + Commodity Watchdog (parallel, advanced mode only)
Stage 4: Surgeon — analyze margins
Stage 5: Advisor — generate strategic advice
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from hephae_common.adk_helpers import user_msg, user_msg_with_image, _strip_markdown_fences

from hephae_agents.margin_analyzer.agent import (
    vision_intake_agent,
    benchmark_and_commodity,
    surgeon_agent,
    advisor_agent,
)

logger = logging.getLogger(__name__)


def _parse_json_safe(text: str) -> Any:
    """Parse JSON from agent output, stripping markdown fences if needed."""
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        clean = _strip_markdown_fences(text)
        return json.loads(clean)


async def run_margin_analysis(
    identity: dict[str, Any],
    business_context: Any | None = None,
    *,
    advanced_mode: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run the full 5-stage margin surgery pipeline.

    Args:
        identity: Enriched identity dict (must have menuScreenshotBase64).
        business_context: Optional BusinessContext with market data.
        advanced_mode: If True, runs Benchmarker + Watchdog LLMs. Otherwise uses estimates.

    Returns:
        Report dict with identity, menu_items, strategic_advice, overall_score.
    """
    # Auto-screenshot menu URL if no base64 screenshot provided
    if not identity.get("menuScreenshotBase64") and identity.get("menuUrl"):
        logger.info(f"[Margin Runner] No screenshot — capturing menu from URL: {identity['menuUrl']}")
        try:
            from hephae_agents.shared_tools.playwright import screenshot_page
            result = await screenshot_page(identity["menuUrl"], quality=70)
            if result.get("screenshot_base64"):
                identity = {**identity, "menuScreenshotBase64": result["screenshot_base64"]}
                logger.info("[Margin Runner] Menu screenshot captured successfully")
            else:
                raise ValueError(f"Screenshot failed: {result.get('error', 'empty result')}")
        except Exception as e:
            raise ValueError(f"Could not screenshot menuUrl ({identity['menuUrl']}): {e}")

    if not identity.get("menuScreenshotBase64"):
        raise ValueError("Missing menuScreenshotBase64 and no menuUrl for margin analysis")

    logger.info("[Margin Runner] Commencing margin surgery...")

    # Load grounding memory from human-curated fixtures
    from hephae_db.eval.grounding import get_agent_memory_service
    memory_service = await get_agent_memory_service("margin_surgeon")

    session_service = kwargs.get("session_service") or InMemorySessionService()
    session_id = f"surgery-{int(time.time() * 1000)}"
    user_id = "hub-user"

    # Pre-load market data from BusinessContext into session state
    initial_state: dict = {}
    if business_context:
        cpi = getattr(business_context, "get_cpi", lambda: None)()
        if cpi:
            initial_state["_market_cpi"] = cpi
        fred = getattr(business_context, "get_fred", lambda: None)()
        if fred:
            initial_state["_market_fred"] = fred
        commodity = getattr(business_context, "get_commodity_data", lambda: None)()
        if commodity:
            initial_state["_market_commodities"] = commodity
        commodity_prices = getattr(business_context, "commodity_prices", None)
        if commodity_prices:
            initial_state["_market_commodity_prices"] = commodity_prices

    await session_service.create_session(
        app_name="hephae-hub", user_id=user_id, session_id=session_id, state=initial_state
    )

    # 1. Vision Intake
    logger.info("[Margin Runner] Step 1: Vision Intake...")
    vision_runner = Runner(app_name="hephae-hub", agent=vision_intake_agent, session_service=session_service, memory_service=memory_service)

    menu_items_prompt = ""
    menu_items: list = []

    b64_data = re.sub(r"^data:image/\w+;base64,", "", identity["menuScreenshotBase64"])

    async for raw_event in vision_runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_msg_with_image("Extract all menu items from this image.", b64_data),
    ):
        actions = getattr(raw_event, "actions", None)
        if actions:
            delta = getattr(actions, "state_delta", None) or (actions if isinstance(actions, dict) else {})
            if isinstance(delta, dict) and delta.get("parsedMenuItems"):
                val = delta["parsedMenuItems"]
                menu_items_prompt = val if isinstance(val, str) else json.dumps(val)

    try:
        logger.info(f"[Margin Runner] Raw Vision Output: {menu_items_prompt[:200]}")
        parsed = _parse_json_safe(menu_items_prompt)
        if parsed is not None:
            menu_items = parsed if isinstance(parsed, list) else []
            menu_items_prompt = json.dumps(parsed)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Vision parse failed")

    if not menu_items:
        raise ValueError("Failed to parse menu items from crawled screenshot.")

    benchmark_prompt = "[]"
    commodity_prompt = "[]"

    if advanced_mode:
        # 2 & 3. Benchmarker + Commodity Watchdog via ADK ParallelAgent
        logger.info("[Margin Runner] Steps 2+3: Benchmarker || CommodityWatchdog (Advanced Mode)...")

        bc_runner = Runner(app_name="hephae-hub", agent=benchmark_and_commodity, session_service=session_service, memory_service=memory_service)
        async for _ in bc_runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_msg(
                f"Here are the parsed menu items for {identity.get('name')} "
                f"in {identity.get('address', 'their local area')}:\n{menu_items_prompt}"
            ),
        ):
            pass

        bc_session = await session_service.get_session(
            app_name="hephae-hub", session_id=session_id, user_id=user_id
        )
        bc_state = bc_session.state or {}
        bv = bc_state.get("competitorBenchmarks", "[]")
        benchmark_prompt = bv if isinstance(bv, str) else json.dumps(bv)
        cv = bc_state.get("commodityTrends", "[]")
        commodity_prompt = cv if isinstance(cv, str) else json.dumps(cv)

    else:
        logger.info("[Margin Runner] Fast Mode: Bypassing Benchmarker and Watchdog LLMs.")
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
    logger.info("[Margin Runner] Step 4: The Surgeon...")
    surgeon_runner = Runner(app_name="hephae-hub", agent=surgeon_agent, session_service=session_service, memory_service=memory_service)
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
        try:
            parsed = _parse_json_safe(surgeon_prompt)
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
    logger.info("[Margin Runner] Step 5: The Advisor...")
    advisor_runner = Runner(app_name="hephae-hub", agent=advisor_agent, session_service=session_service, memory_service=memory_service)
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
                    strategic_advice = _parse_json_safe(raw_adv)
                    if not isinstance(strategic_advice, list):
                        strategic_advice = []
                except (json.JSONDecodeError, ValueError):
                    pass

    logger.info("[Margin Runner] Pipeline complete.")

    # Score Calculation
    total_leakage = sum(item.get("price_leakage", 0) for item in menu_analysis)
    total_revenue = sum(item.get("current_price", 0) for item in menu_analysis)
    score = max(0, min(100, round(100 - (total_leakage / (total_revenue or 1) * 20))))

    import datetime

    return {
        "identity": identity,
        "menu_items": menu_analysis,
        "strategic_advice": strategic_advice,
        "overall_score": score,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
