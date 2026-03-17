"""Weekly Pulse orchestrator — gathers all signals and generates insight-card briefing.

Pipeline:
1. Load existing zip code research (or run fresh if none exists)
2. Gather industry-specific data via plugin registry (BLS, USDA, FDA)
3. Fetch local news via Google News RSS
4. Query Google Trends via BigQuery
5. Load local catalyst data (if available)
6. Load prior week's pulse (for delta detection)
7. Run WeeklyPulseAgent to synthesize all signals into insight cards
8. Save to Firestore
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


async def generate_pulse(
    zip_code: str,
    business_type: str,
    week_of: str = "",
    force: bool = False,
) -> dict[str, Any]:
    """Main entry point for weekly pulse generation.

    Args:
        zip_code: Target zip code (e.g. "07110").
        business_type: Business category (e.g. "Restaurants").
        week_of: ISO date for the week. Defaults to today.
        force: If True, regenerate even if a pulse already exists for this week.

    Returns:
        {"pulse": dict, "pulseId": str, "signalsUsed": list[str]}
    """
    from hephae_db.firestore.research import get_zipcode_report
    from hephae_db.firestore.weekly_pulse import (
        get_latest_pulse,
        save_weekly_pulse,
    )
    from hephae_db.bigquery.reader import query_google_trends
    from hephae_integrations.news_client import query_local_news
    from hephae_agents.research.weekly_pulse_agent import generate_weekly_pulse
    from hephae_api.workflows.orchestrators.industry_plugins import fetch_industry_data
    from hephae_api.workflows.orchestrators.zipcode_research import research_zip_code

    if not week_of:
        week_of = datetime.utcnow().strftime("%Y-%m-%d")

    logger.info(f"[WeeklyPulse] Starting pulse for {zip_code} / {business_type} / {week_of}")

    # 0. Check for existing pulse this week (skip if force)
    if not force:
        existing = await get_latest_pulse(zip_code, business_type)
        if existing and existing.get("weekOf") == week_of:
            logger.info(f"[WeeklyPulse] Returning existing pulse for {week_of}")
            return {
                "pulse": existing.get("pulse", {}),
                "pulseId": existing["id"],
                "signalsUsed": existing.get("signalsUsed", []),
            }

    signals: dict[str, Any] = {}
    signals_used: list[str] = []

    # 1. Load zip code research (run fresh if none cached)
    zip_data = await get_zipcode_report(zip_code)
    if not zip_data and force:
        logger.info(f"[WeeklyPulse] No zip research found — running fresh for {zip_code}")
        try:
            result = await research_zip_code(zip_code, force=True)
            zip_data = {"report": result.get("report", {})}
        except Exception as e:
            logger.error(f"[WeeklyPulse] Zip research failed: {e}")

    if zip_data:
        report = zip_data.get("report", {})
        signals["zipReport"] = report
        signals_used.append("zipcode_research")

        # Extract city/state from geography section for downstream queries
        geo = report.get("sections", {}).get("geography", {})
        city = ""
        state = ""
        if isinstance(geo, dict):
            content = geo.get("content", "")
            # Simple heuristic — extract from key_facts or content
            facts = geo.get("key_facts", [])
            for fact in facts:
                if "city" in fact.lower() or "town" in fact.lower():
                    city = fact.split(":")[-1].strip() if ":" in fact else ""
                if "state" in fact.lower():
                    state = fact.split(":")[-1].strip() if ":" in fact else ""
    else:
        city = ""
        state = ""

    # 2-4. Gather additional signals in parallel
    async def _fetch_industry():
        try:
            return await fetch_industry_data(business_type, state)
        except Exception as e:
            logger.error(f"[WeeklyPulse] Industry data failed: {e}")
            return {}

    async def _fetch_news():
        location = f"{zip_code}"
        if city:
            location = f"{city}, {state}" if state else city
        try:
            return await query_local_news(location, business_type)
        except Exception as e:
            logger.error(f"[WeeklyPulse] News fetch failed: {e}")
            return {}

    async def _fetch_trends():
        # Extract DMA from zip report if available
        report = signals.get("zipReport", {})
        dma_name = ""
        # DMA is sometimes stored in the trending section
        trending = report.get("sections", {}).get("trending", {})
        if isinstance(trending, dict):
            for fact in trending.get("key_facts", []):
                if "DMA" in fact or "dma" in fact.lower():
                    dma_name = fact.split(":")[-1].strip() if ":" in fact else ""
                    break
        if not dma_name:
            return {}
        try:
            result = await query_google_trends(dma_name)
            return result.model_dump(mode="json") if hasattr(result, "model_dump") else result
        except Exception as e:
            logger.error(f"[WeeklyPulse] Trends fetch failed: {e}")
            return {}

    industry_data, news_data, trends_data = await asyncio.gather(
        _fetch_industry(),
        _fetch_news(),
        _fetch_trends(),
    )

    # Merge industry data into signals
    if industry_data:
        signals.update(industry_data)
        for key in industry_data:
            signals_used.append(f"industry:{key}")

    if news_data and news_data.get("articles"):
        signals["localNews"] = news_data
        signals_used.append("local_news")

    if trends_data:
        signals["trends"] = trends_data
        signals_used.append("google_trends")

    # 5. Load prior week's pulse for delta detection
    prior_pulse = None
    try:
        prior = await get_latest_pulse(zip_code, business_type)
        if prior and prior.get("weekOf") != week_of:
            prior_pulse = prior
    except Exception:
        pass

    # 6. Run WeeklyPulseAgent
    logger.info(f"[WeeklyPulse] Gathered {len(signals_used)} signals — running analysis agent")
    pulse = await generate_weekly_pulse(
        zip_code=zip_code,
        business_type=business_type,
        week_of=week_of,
        signals=signals,
        prior_pulse=prior_pulse,
    )

    # 7. Save to Firestore
    pulse_id = await save_weekly_pulse(
        zip_code=zip_code,
        business_type=business_type,
        week_of=week_of,
        pulse=pulse,
        signals_used=signals_used,
    )

    logger.info(f"[WeeklyPulse] Pulse saved as {pulse_id} with {len(pulse.get('insights', []))} insights")

    return {
        "pulse": pulse,
        "pulseId": pulse_id,
        "signalsUsed": signals_used,
    }
