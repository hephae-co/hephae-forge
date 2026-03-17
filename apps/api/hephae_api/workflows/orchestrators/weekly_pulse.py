"""Weekly Pulse orchestrator — gathers all signals and generates insight-card briefing.

Pipeline:
1. Load existing zip code research (or run fresh if none exists)
2. Gather industry-specific data via plugin registry (BLS, USDA, FDA)
3. Fetch local news via Google News RSS
4. Query Google Trends via BigQuery
5. Fetch local catalysts (government signals)
6. Load prior week's pulse (for delta detection)
7. Run WeeklyPulseAgent to synthesize all signals into insight cards
8. Save to Firestore (pulse + raw signal diagnostics for explainability)
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def _truncate(obj: Any, max_len: int = 500) -> Any:
    """Truncate large values for diagnostics storage."""
    if isinstance(obj, str) and len(obj) > max_len:
        return obj[:max_len] + f"... ({len(obj)} chars)"
    if isinstance(obj, list) and len(obj) > 10:
        return obj[:10] + [f"... ({len(obj)} items total)"]
    if isinstance(obj, dict):
        return {k: _truncate(v, max_len) for k, v in obj.items()}
    return obj


async def generate_pulse(
    zip_code: str,
    business_type: str,
    week_of: str = "",
    force: bool = False,
) -> dict[str, Any]:
    """Main entry point for weekly pulse generation.

    Returns:
        {"pulse": dict, "pulseId": str, "signalsUsed": list[str], "diagnostics": dict}
    """
    from hephae_db.firestore.research import get_zipcode_report
    from hephae_db.firestore.weekly_pulse import (
        get_latest_pulse,
        save_weekly_pulse,
    )
    from hephae_db.bigquery.reader import query_google_trends
    from hephae_integrations.news_client import query_local_news
    from hephae_agents.research.weekly_pulse_agent import generate_weekly_pulse
    from hephae_agents.research.local_catalyst import research_local_catalysts
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
                "diagnostics": existing.get("diagnostics", {}),
            }

    signals: dict[str, Any] = {}
    signals_used: list[str] = []
    # Track what happened with each source for explainability
    diagnostics: dict[str, Any] = {
        "sources": {},
        "startedAt": datetime.utcnow().isoformat(),
    }

    def _record(source: str, status: str, detail: str = "", data_preview: Any = None):
        """Record diagnostic info for a data source."""
        entry: dict[str, Any] = {"status": status, "detail": detail}
        if data_preview is not None:
            entry["dataPreview"] = _truncate(data_preview)
        diagnostics["sources"][source] = entry

    # ── 1. Zip code research ─────────────────────────────────────────────
    zip_data = await get_zipcode_report(zip_code)
    if zip_data:
        _record("zipcode_research", "ok", "Loaded from Firestore cache")
    elif not zip_data:
        # Always run zip research if none exists — this is the base layer
        logger.info(f"[WeeklyPulse] No zip research cached — running fresh for {zip_code}")
        try:
            result = await research_zip_code(zip_code, force=True)
            zip_data = {"report": result.get("report", {})}
            _record("zipcode_research", "ok", "Ran fresh research pipeline")
        except Exception as e:
            logger.error(f"[WeeklyPulse] Zip research failed: {e}")
            _record("zipcode_research", "error", str(e))

    city = ""
    state = ""
    dma_name = ""

    if zip_data:
        report = zip_data.get("report", {})
        signals["zipReport"] = report
        signals_used.append("zipcode_research")

        sections = report.get("sections", {})
        section_names = [k for k, v in sections.items() if v] if isinstance(sections, dict) else []
        _record("zipcode_research", "ok",
                f"Loaded with {len(section_names)} sections: {', '.join(section_names)}",
                {"summary": (report.get("summary", "") or "")[:300]})

        # Extract city/state from geography section
        geo = sections.get("geography", {})
        if isinstance(geo, dict):
            facts = geo.get("key_facts", [])
            content = geo.get("content", "")
            for fact in facts:
                fl = fact.lower()
                if ("city" in fl or "town" in fl or "village" in fl) and ":" in fact:
                    city = fact.split(":")[-1].strip()
                if "state" in fl and ":" in fact:
                    state = fact.split(":")[-1].strip()
            # Fallback: try to extract from content
            if not city and content:
                # Often the first sentence mentions the location
                city = zip_code  # Use zip as fallback location label

        # Extract DMA from trending section
        trending = sections.get("trending", {})
        if isinstance(trending, dict):
            for fact in trending.get("key_facts", []):
                if "DMA" in fact or "dma" in fact.lower() or "market" in fact.lower():
                    if ":" in fact:
                        dma_name = fact.split(":")[-1].strip()
                        break
            # Also check content
            if not dma_name:
                tcontent = trending.get("content", "")
                if "New York" in tcontent:
                    dma_name = "New York"
                elif "Philadelphia" in tcontent:
                    dma_name = "Philadelphia"

    # ── 2-5. Gather additional signals in parallel ───────────────────────

    async def _fetch_industry() -> dict[str, Any]:
        try:
            result = await fetch_industry_data(business_type, state)
            if result:
                details = []
                for k, v in result.items():
                    if k == "priceDeltas":
                        details.append(f"{len(v)} price deltas")
                    elif k == "blsCpi":
                        series_count = len(v.get("series", []))
                        highlights = v.get("highlights", [])
                        details.append(f"BLS: {series_count} series, {len(highlights)} highlights")
                    elif k == "fdaRecalls":
                        details.append(f"FDA: {v.get('totalRecalls', 0)} recalls")
                    elif k == "usdaPrices":
                        details.append(f"USDA: {len(v.get('commodities', []))} commodities")
                _record("industry_data", "ok", "; ".join(details), {k: type(v).__name__ for k, v in result.items()})
            else:
                _record("industry_data", "empty", "All industry sources returned empty")
            return result
        except Exception as e:
            _record("industry_data", "error", str(e))
            logger.error(f"[WeeklyPulse] Industry data failed: {e}")
            return {}

    async def _fetch_news() -> dict[str, Any]:
        location = city if city else zip_code
        if city and state:
            location = f"{city}, {state}"
        try:
            result = await query_local_news(location, business_type)
            article_count = len(result.get("articles", []))
            if article_count > 0:
                headlines = [a.get("headline", "") for a in result["articles"][:5]]
                _record("local_news", "ok", f"{article_count} articles for '{location}'",
                        {"headlines": headlines})
            else:
                _record("local_news", "empty", f"No articles found for '{location}'")
            return result
        except Exception as e:
            _record("local_news", "error", str(e))
            logger.error(f"[WeeklyPulse] News fetch failed: {e}")
            return {}

    async def _fetch_trends() -> dict[str, Any]:
        if not dma_name:
            _record("google_trends", "skipped", "No DMA name extracted from zip report")
            return {}
        try:
            result = await query_google_trends(dma_name)
            data = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
            top_count = len(data.get("topTerms", []))
            rising_count = len(data.get("risingTerms", []))
            if top_count or rising_count:
                _record("google_trends", "ok",
                        f"DMA '{dma_name}': {top_count} top, {rising_count} rising terms",
                        {"topTerms": data.get("topTerms", [])[:5]})
            else:
                _record("google_trends", "empty", f"No trends for DMA '{dma_name}'")
            return data
        except Exception as e:
            _record("google_trends", "error", str(e))
            logger.error(f"[WeeklyPulse] Trends fetch failed: {e}")
            return {}

    async def _fetch_catalysts() -> dict[str, Any]:
        loc_city = city if city else zip_code
        loc_state = state if state else "NJ"  # TODO: resolve from zip
        try:
            result = await research_local_catalysts(loc_city, loc_state, business_type)
            catalyst_count = len(result.get("catalysts", []))
            if catalyst_count > 0:
                _record("local_catalysts", "ok",
                        f"{catalyst_count} catalysts found",
                        {"summary": result.get("summary", ""), "catalysts": result.get("catalysts", [])[:3]})
            else:
                _record("local_catalysts", "empty", result.get("summary", "No catalysts found"))
            return result
        except Exception as e:
            _record("local_catalysts", "error", str(e))
            logger.error(f"[WeeklyPulse] Catalyst fetch failed: {e}")
            return {}

    industry_data, news_data, trends_data, catalyst_data = await asyncio.gather(
        _fetch_industry(),
        _fetch_news(),
        _fetch_trends(),
        _fetch_catalysts(),
    )

    # Merge results into signals
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

    if catalyst_data and catalyst_data.get("catalysts"):
        signals["localCatalysts"] = catalyst_data
        signals_used.append("local_catalysts")

    # ── 6. Prior week's pulse for delta detection ────────────────────────
    prior_pulse = None
    try:
        prior = await get_latest_pulse(zip_code, business_type)
        if prior and prior.get("weekOf") != week_of:
            prior_pulse = prior
            _record("prior_pulse", "ok", f"Found prior pulse from {prior.get('weekOf', '?')}")
        else:
            _record("prior_pulse", "skipped", "No prior pulse available (first run or same week)")
    except Exception:
        _record("prior_pulse", "skipped", "Could not load prior pulse")

    # ── 7. Run WeeklyPulseAgent ──────────────────────────────────────────
    diagnostics["signalCount"] = len(signals_used)
    diagnostics["agentInputKeys"] = list(signals.keys())

    logger.info(f"[WeeklyPulse] Gathered {len(signals_used)} signals — running analysis agent")
    pulse = await generate_weekly_pulse(
        zip_code=zip_code,
        business_type=business_type,
        week_of=week_of,
        signals=signals,
        prior_pulse=prior_pulse,
    )

    diagnostics["completedAt"] = datetime.utcnow().isoformat()
    diagnostics["insightCount"] = len(pulse.get("insights", []))

    # ── 8. Save to Firestore ─────────────────────────────────────────────
    pulse_id = await save_weekly_pulse(
        zip_code=zip_code,
        business_type=business_type,
        week_of=week_of,
        pulse=pulse,
        signals_used=signals_used,
        diagnostics=diagnostics,
    )

    logger.info(f"[WeeklyPulse] Pulse saved as {pulse_id} with {len(pulse.get('insights', []))} insights")

    return {
        "pulse": pulse,
        "pulseId": pulse_id,
        "signalsUsed": signals_used,
        "diagnostics": diagnostics,
    }
