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


async def _extract_menu_from_html(url: str) -> list[dict]:
    """
    Fallback: download a menu URL as HTML and extract items using Gemini text model.
    Used when the screenshot vision agent returns an empty menu.
    """
    import os
    import httpx
    from hephae_common.adk_helpers import _strip_markdown_fences

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible)"})
            html = resp.text
    except Exception as e:
        logger.warning(f"[HTML Extract] Failed to fetch {url}: {e}")
        return []

    # Strip scripts/styles and condense whitespace
    html_clean = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL)
    html_clean = re.sub(r"<[^>]+>", " ", html_clean)
    html_clean = re.sub(r"\s+", " ", html_clean).strip()

    # Quick check — if fewer than 3 price patterns, not worth calling LLM
    if len(re.findall(r"\$\s*\d+\.?\d*", html_clean)) < 3:
        return []

    # Cap HTML at 8000 chars to stay within context limits
    html_snippet = html_clean[:8000]

    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        return []

    payload = {
        "contents": [{
            "parts": [{
                "text": (
                    "Extract all food menu items with prices from the following text (from a restaurant website).\n"
                    "Return ONLY a JSON array. Each object must have: item_name, current_price (number), category, description.\n"
                    "Do not include items without a clear price. Output only the JSON array, no markdown.\n\n"
                    f"{html_snippet}"
                )
            }]
        }],
        "generationConfig": {"temperature": 0},
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key={gemini_key}",
                json=payload,
            )
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            clean = _strip_markdown_fences(text)
            parsed = json.loads(clean)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                for v in parsed.values():
                    if isinstance(v, list):
                        return v
    except Exception as e:
        logger.warning(f"[HTML Extract] Gemini extraction failed: {e}")

    return []


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
            if isinstance(parsed, list):
                menu_items = parsed
            elif isinstance(parsed, dict):
                # MenuIntakeOutput schema wraps items in {"items": [...]}
                menu_items = parsed.get("items") or []
                for key, val in parsed.items():
                    if isinstance(val, list) and val:
                        menu_items = val
                        break
            menu_items_prompt = json.dumps(menu_items)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Vision parse failed")

    # Fallback: if screenshot vision returned nothing, try HTML text extraction
    if not menu_items and identity.get("menuUrl"):
        logger.info("[Margin Runner] Vision returned empty — trying HTML text extraction fallback...")
        try:
            menu_items = await _extract_menu_from_html(identity["menuUrl"])
            if menu_items:
                menu_items_prompt = json.dumps(menu_items)
                logger.info(f"[Margin Runner] HTML extraction found {len(menu_items)} items")
        except Exception as e:
            logger.warning(f"[Margin Runner] HTML extraction failed: {e}")

    if not menu_items:
        raise ValueError("Failed to parse menu items from crawled screenshot.")

    benchmark_prompt = "[]"
    commodity_prompt = "[]"

    if advanced_mode:
        # 2 & 3. Benchmarker + Commodity Watchdog via ADK ParallelAgent
        logger.info("[Margin Runner] Steps 2+3: Benchmarker || CommodityWatchdog (Advanced Mode)...")

        # Extract competitor names from identity so benchmarker can search for real prices
        competitors_raw = identity.get("competitors") or []
        if isinstance(competitors_raw, list):
            competitor_names = [
                c.get("name", "") if isinstance(c, dict) else str(c)
                for c in competitors_raw
                if c
            ]
        else:
            competitor_names = []

        bc_runner = Runner(app_name="hephae-hub", agent=benchmark_and_commodity, session_service=session_service, memory_service=memory_service)
        async for _ in bc_runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_msg(
                f"Restaurant: {identity.get('name')}\n"
                f"Location: {identity.get('address', 'their local area')}\n"
                f"Known competitors: {', '.join(competitor_names) if competitor_names else 'none provided'}\n\n"
                f"Parsed menu items:\n{menu_items_prompt}"
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
        logger.info("[Margin Runner] Fast Mode: Using cuisine-aware estimates + commodity data.")
        from hephae_agents.margin_analyzer.tools import _estimate_cuisine_medians, _infer_commodities_from_terms
        import asyncio

        item_names = [item.get("item_name", "") for item in menu_items]
        cuisine_benchmarks = _estimate_cuisine_medians(
            identity.get("address", "New Jersey"), item_names
        )
        benchmark_prompt = json.dumps({
            "competitors": cuisine_benchmarks,
            "macroeconomic_context": {
                "analysis_hint": "Cuisine-aware area estimates. Accuracy: medium.",
            },
        })

        # Still run real commodity data even in fast mode
        commodity_set = _infer_commodities_from_terms(
            item_names + [item.get("category", "") for item in menu_items]
        )
        commodity_results = []
        from hephae_agents.market_data import fetch_commodity_prices
        for comm in list(commodity_set)[:6]:  # cap at 6 to stay fast
            try:
                data = await fetch_commodity_prices(comm)
                if data and data.get("commodity"):
                    trend_str = data.get("trend30Day", "0%")
                    import re as _re
                    inflation_val = float(_re.sub(r"[^0-9.\-]", "", trend_str) or "2.4")
                    commodity_results.append({
                        "ingredient": data["commodity"].upper(),
                        "inflation_rate_12mo": inflation_val,
                        "trend_description": (
                            f"BLS Retail Price: {data.get('pricePerUnit')}. "
                            f"Trend: {data.get('trend30Day')}."
                        ),
                    })
            except Exception:
                pass
        if not commodity_results:
            commodity_results = [{"ingredient": "GENERAL", "inflation_rate_12mo": 3.2,
                                   "trend_description": "National food-at-home inflation estimate."}]
        commodity_prompt = json.dumps(commodity_results)

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
    strategic_advice: dict = {}

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
                    parsed_adv = _parse_json_safe(raw_adv)
                    if isinstance(parsed_adv, dict):
                        strategic_advice = parsed_adv
                    elif isinstance(parsed_adv, list):
                        strategic_advice = {"recommendations": parsed_adv}
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
