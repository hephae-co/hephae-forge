"""POST /api/analyze — Full margin surgery pipeline."""

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

from backend.lib.auth import verify_request

from hephae_capabilities.margin_analyzer import (
    vision_intake_agent,
    benchmarker_agent,
    commodity_watchdog_agent,
    surgeon_agent,
    advisor_agent,
)
from hephae_capabilities.discovery import LocatorAgent
from hephae_capabilities.business_profiler import ProfilerAgent
from hephae_capabilities.social.marketing_swarm import generate_and_draft_marketing_content
from hephae_common.report_storage import generate_slug, upload_report
from hephae_common.report_templates import build_margin_report
from hephae_db.firestore.agent_results import write_agent_result
from hephae_db.context.business_context import build_business_context
from backend.config import AgentVersions
from hephae_common.adk_helpers import user_msg, user_msg_with_image
from hephae_common.model_config import AgentModels
from backend.types import SurgicalReport as SurgicalReportModel

logger = logging.getLogger(__name__)

router = APIRouter()


def _clean_json(text: str) -> str:
    return re.sub(r"```json\s*|\s*```", "", text).strip()


async def _scrape_menu_screenshot(official_url: str) -> str | None:
    """Scrape a full-page JPEG screenshot of the menu page."""
    from hephae_capabilities.shared_tools import screenshot_page

    result = await screenshot_page(official_url)
    return result.get("screenshot_base64") or None


async def _download_screenshot_as_base64(url: str) -> str | None:
    """Download a JPEG from GCS URL and return as base64 string."""
    import httpx
    import base64

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(url)
            if res.status_code == 200 and len(res.content) > 1000:
                return base64.b64encode(res.content).decode()
    except Exception as e:
        logger.warning(f"[API/Analyze] Failed to download screenshot from {url}: {e}")
    return None


async def _scrape_menu_text(url: str) -> str | None:
    """Crawl a menu page and return its text/markdown content."""
    from hephae_capabilities.shared_tools.crawl4ai import crawl_with_options

    try:
        result = await crawl_with_options(
            url=url,
            scan_full_page=True,
            process_iframes=True,
            remove_overlays=True,
        )
        markdown = result.get("markdown", "")
        if markdown and len(markdown) > 100:
            logger.info(f"[API/Analyze] Got {len(markdown)} chars of menu text from {url}")
            return markdown[:15000]  # Cap to prevent excessive tokens
    except Exception as e:
        logger.warning(f"[API/Analyze] Text crawl failed for {url}: {e}")
    return None


async def _search_menu_text(business_name: str) -> str | None:
    """Search Google for the business menu and scrape from third-party sites."""
    from hephae_capabilities.shared_tools.google_search import google_search
    from hephae_capabilities.shared_tools.crawl4ai import crawl_with_options

    try:
        search_result = await google_search(f"{business_name} menu prices")
        if not search_result or search_result.get("error"):
            return None

        sources = search_result.get("sources", [])

        # First pass: try known menu aggregator sources
        for item in sources:
            url = item.get("url", "")
            if not url:
                continue
            if any(d in url for d in ["yelp.com", "doordash.com", "grubhub.com", "ubereats.com",
                                       "allmenus.com", "menupages.com", "seamless.com"]):
                try:
                    result = await crawl_with_options(url=url, remove_overlays=True)
                    markdown = result.get("markdown", "")
                    if markdown and len(markdown) > 200:
                        logger.info(f"[API/Analyze] Got menu text from {url} ({len(markdown)} chars)")
                        return markdown[:15000]
                except Exception:
                    continue

        # Second pass: try any source URL
        for item in sources[:3]:
            url = item.get("url", "")
            if not url:
                continue
            try:
                result = await crawl_with_options(url=url, remove_overlays=True)
                markdown = result.get("markdown", "")
                if markdown and len(markdown) > 200:
                    logger.info(f"[API/Analyze] Got menu text from {url} ({len(markdown)} chars)")
                    return markdown[:15000]
            except Exception:
                continue

        # Last resort: the search result text itself may contain menu data
        result_text = search_result.get("result", "")
        if result_text and len(result_text) > 200:
            logger.info(f"[API/Analyze] Using search result text as menu data ({len(result_text)} chars)")
            return result_text[:15000]

    except Exception as e:
        logger.warning(f"[API/Analyze] Menu search failed for {business_name}: {e}")
    return None


async def _extract_menu_items_from_text(menu_text: str, business_name: str) -> list[dict]:
    """Use an LLM to extract structured menu items from raw text/markdown."""
    import os
    from google import genai
    from google.genai import types as genai_types
    from hephae_common.model_fallback import generate_with_fallback

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return []

    client = genai.Client(api_key=api_key)
    prompt = f"""Extract all menu items with prices from the following text for {business_name}.

Return ONLY a JSON array where each object has:
- "item_name": string (the dish/drink name)
- "current_price": number (the price as a decimal, e.g. 12.99)
- "category": string (e.g. "Appetizers", "Main Course", "Drinks", "Desserts")
- "description": string (brief description if available, else empty string)

If a price range is given, use the lower price. Skip items without prices.
Extract at least the first 20 items you can find.

MENU TEXT:
{menu_text}

Return ONLY the JSON array, no markdown fences or other text."""

    try:
        result = await generate_with_fallback(
            client,
            model=AgentModels.PRIMARY_MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(),
        )
        raw = _clean_json(result.text or "")
        items = json.loads(raw)
        if isinstance(items, list) and len(items) > 0:
            logger.info(f"[API/Analyze] Extracted {len(items)} menu items from text")
            return items
    except Exception as e:
        logger.warning(f"[API/Analyze] Text menu extraction failed: {e}")
    return []


@router.post("/analyze", response_model=SurgicalReportModel, dependencies=[Depends(verify_request)])
async def analyze(request: Request):
    try:
        body = await request.json()
        url = body.get("url")
        enriched_profile = body.get("enrichedProfile")
        advanced_mode = body.get("advancedMode", False)

        # FAST PATH: We already ran the Parallel Discovery Subagents
        if enriched_profile and enriched_profile.get("officialUrl"):
            logger.info(f"[API/Analyze] Fast Path: Bypassing Profiler for {enriched_profile.get('name')}")
            ctx = await build_business_context({**enriched_profile}, capabilities=["margin"])
            identity = ctx.identity

            # Get menu screenshot: GCS URL (from discovery) → Playwright fallback
            if not identity.get("menuScreenshotBase64"):
                # Try downloading the already-captured screenshot from GCS
                gcs_url = identity.get("menuScreenshotUrl")
                if gcs_url:
                    logger.info(f"[API/Analyze] Fast Path: Downloading existing screenshot from GCS")
                    screenshot = await _download_screenshot_as_base64(gcs_url)
                    if screenshot:
                        identity["menuScreenshotBase64"] = screenshot

            if not identity.get("menuScreenshotBase64"):
                # Fallback: take a fresh screenshot with Playwright
                target_url = identity.get("menuUrl") or identity["officialUrl"]
                logger.info(f"[API/Analyze] Fast Path: Screenshotting {target_url}")
                screenshot = await _scrape_menu_screenshot(target_url)
                if screenshot:
                    identity["menuScreenshotBase64"] = screenshot

            # Ensure colors/persona are populated
            identity.setdefault("primaryColor", "#0f172a")
            identity.setdefault("secondaryColor", "#334155")
            identity.setdefault("persona", "Local Business")

        else:
            # SLOW PATH: Legacy sequential flow (no enriched profile provided)
            logger.info(f"[API/Analyze] Slow Path: Analyzing identity and crawling menu for: {url}")
            base_identity = await LocatorAgent.resolve(url or "")
            identity = await ProfilerAgent.profile(base_identity)
            ctx = await build_business_context(identity, capabilities=["margin"])

        # --- Set up session service for all paths ---
        session_service = InMemorySessionService()
        session_id = f"surgery-{int(time.time() * 1000)}"
        user_id = "hub-user"

        initial_state: dict = {}
        if ctx:
            cpi = ctx.get_cpi()
            if cpi:
                initial_state["_market_cpi"] = cpi
            fred = ctx.get_fred()
            if fred:
                initial_state["_market_fred"] = fred
            commodity = ctx.get_commodity_data()
            if commodity:
                initial_state["_market_commodities"] = commodity
            if ctx.commodity_prices:
                initial_state["_market_commodity_prices"] = ctx.commodity_prices

        await session_service.create_session(
            app_name="hephae-hub", user_id=user_id, session_id=session_id, state=initial_state
        )

        # --- Menu item extraction: screenshot path OR text fallback ---
        menu_items: list = []
        menu_items_prompt = ""

        if identity.get("menuScreenshotBase64"):
            # PRIMARY: Vision-based extraction from screenshot
            logger.info("[API/Analyze] Step 1: Vision Intake from screenshot...")

            vision_runner = Runner(app_name="hephae-hub", agent=vision_intake_agent, session_service=session_service)
            b64_data = re.sub(r"^data:image/\w+;base64,", "", identity["menuScreenshotBase64"])

            async for raw_event in vision_runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_msg_with_image("Extract all menu items from this image.", b64_data),
            ):
                event = raw_event
                actions = getattr(event, "actions", None)
                if actions:
                    delta = getattr(actions, "state_delta", None) or (actions if isinstance(actions, dict) else {})
                    if isinstance(delta, dict) and delta.get("parsedMenuItems"):
                        val = delta["parsedMenuItems"]
                        menu_items_prompt = val if isinstance(val, str) else json.dumps(val)

            try:
                logger.info(f"[API/Analyze] Raw Vision Output: {menu_items_prompt[:200]}")
                menu_items_prompt = _clean_json(menu_items_prompt)
                menu_items = json.loads(menu_items_prompt)
            except (json.JSONDecodeError, ValueError):
                logger.warning("[API/Analyze] Vision parse failed, will try text fallback")

        # FALLBACK: Text-based menu extraction
        if not menu_items:
            business_name = identity.get("name", "")
            logger.info(f"[API/Analyze] No screenshot menu — trying text-based extraction for {business_name}")

            # Try crawling the menu URL or official URL
            menu_text = None
            target_url = identity.get("menuUrl") or identity.get("officialUrl")
            if target_url:
                menu_text = await _scrape_menu_text(target_url)

            # If menu URL text was thin, also try the official URL
            if not menu_text and identity.get("menuUrl") and identity.get("officialUrl"):
                menu_text = await _scrape_menu_text(identity["officialUrl"])

            # Last resort: search Google for the menu
            if not menu_text and business_name:
                logger.info(f"[API/Analyze] Searching Google for {business_name} menu...")
                menu_text = await _search_menu_text(business_name)

            if menu_text:
                menu_items = await _extract_menu_items_from_text(menu_text, business_name)
                if menu_items:
                    menu_items_prompt = json.dumps(menu_items)

        if not menu_items:
            return JSONResponse(
                {"error": "Could not find menu items. The business website may not have a public menu, and no menu was found on third-party sites."},
                status_code=422,
            )

        if not menu_items_prompt:
            menu_items_prompt = json.dumps(menu_items)

        benchmark_prompt = "[]"
        commodity_prompt = "[]"

        if advanced_mode:
            # 2 & 3. Benchmarker + Commodity Watchdog (parallel — both read parsedMenuItems)
            logger.info("[API/Analyze] Steps 2+3: Benchmarker || CommodityWatchdog (Advanced Mode)...")

            async def _run_benchmarker():
                result = "[]"
                br = Runner(app_name="hephae-hub", agent=benchmarker_agent, session_service=session_service)
                async for raw_event in br.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=user_msg(
                        f"Here are the parsed menu items for {identity.get('name')} "
                        f"in {identity.get('address', 'their local area')}:\n{menu_items_prompt}"
                    ),
                ):
                    actions = getattr(raw_event, "actions", None)
                    if actions:
                        delta = getattr(actions, "state_delta", None) or (actions if isinstance(actions, dict) else {})
                        if isinstance(delta, dict) and delta.get("competitorBenchmarks"):
                            val = delta["competitorBenchmarks"]
                            result = val if isinstance(val, str) else json.dumps(val)
                return _clean_json(result)

            async def _run_commodity_watchdog():
                result = "[]"
                cr = Runner(app_name="hephae-hub", agent=commodity_watchdog_agent, session_service=session_service)
                async for raw_event in cr.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=user_msg(f"Here are the parsed menu items:\n{menu_items_prompt}"),
                ):
                    actions = getattr(raw_event, "actions", None)
                    if actions:
                        delta = getattr(actions, "state_delta", None) or (actions if isinstance(actions, dict) else {})
                        if isinstance(delta, dict) and delta.get("commodityTrends"):
                            val = delta["commodityTrends"]
                            result = val if isinstance(val, str) else json.dumps(val)
                return _clean_json(result)

            benchmark_prompt, commodity_prompt = await asyncio.gather(
                _run_benchmarker(),
                _run_commodity_watchdog(),
            )

        else:
            logger.info("[API/Analyze] Fast Mode: Bypassing Benchmarker and Watchdog LLMs.")
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
        logger.info("[API/Analyze] Step 4: The Surgeon...")
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
            event = raw_event
            content = getattr(event, "content", None)
            if content and hasattr(content, "parts"):
                for part in content.parts:
                    fr = getattr(part, "function_response", None)
                    if fr and getattr(fr, "name", None) == "perform_margin_surgery":
                        menu_analysis = fr.response

            actions = getattr(event, "actions", None)
            if actions:
                delta = getattr(actions, "state_delta", None) or (actions if isinstance(actions, dict) else {})
                if isinstance(delta, dict) and delta.get("menuAnalysis") and not menu_analysis:
                    val = delta["menuAnalysis"]
                    surgeon_prompt = val if isinstance(val, str) else json.dumps(val)

        if not menu_analysis and surgeon_prompt:
            surgeon_prompt = _clean_json(surgeon_prompt)
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
                logger.warning(f"Raw Surgeon Output: {surgeon_prompt[:300]}")

        # 5. Advisor
        logger.info("[API/Analyze] Step 5: The Advisor...")
        advisor_runner = Runner(app_name="hephae-hub", agent=advisor_agent, session_service=session_service)
        strategic_advice: list = []

        async for raw_event in advisor_runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_msg(f"Here is the menuAnalysis from the Surgeon:\n{surgeon_prompt}"),
        ):
            event = raw_event
            actions = getattr(event, "actions", None)
            if actions:
                delta = getattr(actions, "state_delta", None) or (actions if isinstance(actions, dict) else {})
                if isinstance(delta, dict) and delta.get("strategicAdvice"):
                    val = delta["strategicAdvice"]
                    raw_adv = val if isinstance(val, str) else json.dumps(val)
                    try:
                        strategic_advice = json.loads(_clean_json(raw_adv))
                    except (json.JSONDecodeError, ValueError):
                        pass

        logger.info("[API/Analyze] ADK Margin Surgery Finished.")

        # Score Calculation
        total_leakage = sum(item.get("price_leakage", 0) for item in menu_analysis)
        total_revenue = sum(item.get("current_price", 0) for item in menu_analysis)
        score = max(0, min(100, round(100 - (total_leakage / (total_revenue or 1) * 20))))

        report = {
            "identity": identity,
            "menu_items": menu_analysis,
            "strategic_advice": strategic_advice,
            "overall_score": score,
            "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        }

        # Fire and forget the marketing pipeline
        asyncio.create_task(
            generate_and_draft_marketing_content(report, "Margin Surgery")
        )

        slug = generate_slug(identity.get("name", "unknown"))

        # Upload HTML report to GCS
        report_url = await upload_report(
            slug=slug,
            report_type="margin",
            html_content=build_margin_report(report),
            identity=identity,
            summary=f"${total_leakage:,.0f} profit leakage detected. Score: {score}/100",
        )

        # Strip binary blobs before writing to DB
        safe_identity = {k: v for k, v in identity.items() if k != "menuScreenshotBase64"}
        safe_report = {**report, "identity": safe_identity}

        asyncio.create_task(
            write_agent_result(
                business_slug=slug,
                business_name=identity.get("name", "unknown"),
                agent_name="margin_surgeon",
                agent_version=AgentVersions.MARGIN_SURGEON,
                triggered_by="user",
                score=score,
                summary=f"${total_leakage:,.0f} profit leakage. Score: {score}/100",
                report_url=report_url or None,
                kpis={"totalLeakage": total_leakage},
                raw_data=safe_report,
            )
        )

        result = {**report}
        if report_url:
            result["reportUrl"] = report_url

        return JSONResponse(result)

    except Exception as exc:
        logger.error(f"[API/Analyze] Orchestration Failed: {exc}")
        return JSONResponse({"error": "Internal Server Error"}, status_code=500)
