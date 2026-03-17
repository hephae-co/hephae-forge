"""Weekly Pulse orchestrator — gathers all signals and generates insight-card briefing.

Pipeline:
1. Load existing zip code research (or run fresh)
2. Fetch 7-day weather forecast (NWS API)
3. Gather industry-specific data via plugin registry:
   - BLS CPI (food prices, v1 no-key or v2 with key)
   - USDA NASS (agricultural commodity prices)
   - FDA (food safety recalls)
   - Yelp Fusion (competition density, ratings, new entrants)
   - SBA loans (new business formation signals)
   - EIA (energy costs — state level)
   - FBI UCR (crime/safety — county level)
   - SchoolDigger (education/economic stress)
4. Fetch local news (Google News RSS)
5. Query Google Trends (BigQuery DMA data)
6. Fetch local catalysts (government signals via search + crawl)
7. Fetch NJ legal notices (if NJ zip)
8. Load prior week's pulse (delta detection)
9. Run WeeklyPulseAgent with all signals
10. Save to Firestore with full diagnostics
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
    from hephae_db.firestore.weekly_pulse import get_latest_pulse, save_weekly_pulse
    from hephae_db.bigquery.reader import query_google_trends
    from hephae_db.bigquery.public_data import resolve_zip_geography
    from hephae_integrations.news_client import query_local_news
    from hephae_agents.research.weekly_pulse_agent import generate_weekly_pulse
    from hephae_agents.research.local_catalyst import research_local_catalysts
    from hephae_api.workflows.orchestrators.industry_plugins import fetch_industry_data
    from hephae_api.workflows.orchestrators.zipcode_research import research_zip_code

    if not week_of:
        week_of = datetime.utcnow().strftime("%Y-%m-%d")

    logger.info(f"[WeeklyPulse] Starting pulse for {zip_code} / {business_type} / {week_of}")

    # 0. Check cache
    if not force:
        existing = await get_latest_pulse(zip_code, business_type)
        if existing and existing.get("weekOf") == week_of:
            logger.info(f"[WeeklyPulse] Returning cached pulse for {week_of}")
            return {
                "pulse": existing.get("pulse", {}),
                "pulseId": existing["id"],
                "signalsUsed": existing.get("signalsUsed", []),
                "diagnostics": existing.get("diagnostics", {}),
            }

    signals: dict[str, Any] = {}
    signals_used: list[str] = []
    diagnostics: dict[str, Any] = {"sources": {}, "startedAt": datetime.utcnow().isoformat()}

    def _record(source: str, status: str, detail: str = "", data_preview: Any = None):
        entry: dict[str, Any] = {"status": status, "detail": detail}
        if data_preview is not None:
            entry["dataPreview"] = _truncate(data_preview)
        diagnostics["sources"][source] = entry

    # ── 1. Zip code research ─────────────────────────────────────────
    zip_data = await get_zipcode_report(zip_code)
    if zip_data:
        _record("zipcode_research", "ok", "Loaded from Firestore cache")
    else:
        logger.info(f"[WeeklyPulse] No zip research cached — running fresh for {zip_code}")
        try:
            result = await research_zip_code(zip_code, force=True)
            zip_data = {"report": result.get("report", {})}
            _record("zipcode_research", "ok", "Ran fresh research pipeline")
        except Exception as e:
            logger.error(f"[WeeklyPulse] Zip research failed: {e}")
            _record("zipcode_research", "error", str(e))

    # ── 1a. BQ geography resolution (authoritative — replaces key_facts parsing)
    latitude = 0.0
    longitude = 0.0
    city = ""
    state = ""
    county = ""
    dma_name = ""

    try:
        geo = await resolve_zip_geography(zip_code)
        if geo:
            latitude = geo.latitude
            longitude = geo.longitude
            city = geo.city
            state = geo.state_code
            county = geo.county
            # Resolve DMA from state (most common mapping)
            STATE_TO_DMA = {
                "NJ": "New York", "NY": "New York", "CT": "New York",
                "PA": "Philadelphia", "DE": "Philadelphia",
                "CA": "Los Angeles", "IL": "Chicago", "TX": "Dallas",
                "MA": "Boston", "FL": "Miami", "GA": "Atlanta",
                "WA": "Seattle", "CO": "Denver", "AZ": "Phoenix",
                "DC": "Washington", "MD": "Washington", "VA": "Washington",
            }
            dma_name = STATE_TO_DMA.get(geo.state_code, "")
            _record("bq_geography", "ok",
                    f"{city}, {state} ({county}), DMA={dma_name or 'unknown'}, lat={latitude:.4f}, lon={longitude:.4f}")
        else:
            _record("bq_geography", "empty", f"No geography found for {zip_code}")
    except Exception as e:
        _record("bq_geography", "error", str(e))

    if zip_data:
        report = zip_data.get("report", {})
        signals["zipReport"] = report
        signals_used.append("zipcode_research")

        sections = report.get("sections", {})
        section_names = [k for k, v in sections.items() if v] if isinstance(sections, dict) else []
        _record("zipcode_research", "ok",
                f"{len(section_names)} sections: {', '.join(section_names)}",
                {"summary": (report.get("summary", "") or "")[:300]})

        # Extract DMA from trending section (still needed for Google Trends)
        trending = sections.get("trending", {}) if isinstance(sections, dict) else {}
        if isinstance(trending, dict):
            for fact in trending.get("key_facts", []):
                if any(k in fact.lower() for k in ["dma", "market area", "designated market"]):
                    if ":" in fact:
                        dma_name = fact.split(":")[-1].strip()
                        break
            if not dma_name:
                tcontent = trending.get("content", "")
                for metro in ["New York", "Philadelphia", "Los Angeles", "Chicago", "Boston", "San Francisco", "Washington", "Dallas", "Houston", "Atlanta"]:
                    if metro in tcontent:
                        dma_name = metro
                        break

    # ── 2-7. Gather ALL signals in parallel ──────────────────────────

    async def _fetch_weather() -> dict[str, Any]:
        try:
            from hephae_integrations.nws_client import query_weather_forecast
            result = await query_weather_forecast(zip_code)
            if result and result.get("forecast"):
                _record("weather_nws", "ok",
                        f"{len(result['forecast'])} periods, outdoor: {result.get('outdoorFavorability', '?')}",
                        {"summary": result.get("summary", ""), "alerts": result.get("alerts", [])})
                return result
            _record("weather_nws", "empty", "No forecast data returned")
            return {}
        except ImportError:
            _record("weather_nws", "skipped", "nws_client not installed")
            return {}
        except Exception as e:
            _record("weather_nws", "error", str(e))
            return {}

    async def _fetch_industry() -> dict[str, Any]:
        try:
            result = await fetch_industry_data(
                business_type, state, zip_code, county, latitude, longitude,
            )
            if result:
                details = []
                for k, v in result.items():
                    if k == "priceDeltas":
                        details.append(f"{len(v)} price deltas")
                    elif k == "blsCpi":
                        series_ct = len(v.get("series", []))
                        hl_ct = len(v.get("highlights", []))
                        details.append(f"BLS: {series_ct} series, {hl_ct} highlights")
                    elif k == "fdaRecalls":
                        details.append(f"FDA: {v.get('totalRecalls', 0)} recalls")
                    elif k == "usdaPrices":
                        details.append(f"USDA: {len(v.get('commodities', []))} commodities")
                    elif k == "yelpData":
                        details.append(f"Yelp: {v.get('totalBusinesses', 0)} businesses")
                    elif k == "sbaLoans":
                        details.append(f"SBA: {v.get('recentLoans', 0)} loans")
                    elif k == "energyCosts":
                        details.append(f"EIA: {v.get('latestPrice', '?')} c/kWh")
                    elif k == "crimeStats":
                        details.append(f"FBI: safety={v.get('safetyLevel', '?')}")
                    elif k == "educationData":
                        details.append(f"Edu: stress={v.get('economicStressLevel', '?')}")
                _record("industry_data", "ok", "; ".join(details))
                # Record individual source diagnostics
                for k, v in result.items():
                    if k not in ("priceDeltas",):
                        _record(f"industry:{k}", "ok", details[0] if details else "data present",
                                _truncate(v, 200) if isinstance(v, (dict, list)) else None)
            else:
                _record("industry_data", "empty", "All industry sources returned empty")
            return result
        except Exception as e:
            _record("industry_data", "error", str(e))
            return {}

    async def _fetch_news() -> dict[str, Any]:
        location = f"{city}, {state}" if city and state else (city or zip_code)
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
            return {}

    async def _fetch_trends() -> dict[str, Any]:
        if not dma_name:
            _record("google_trends", "skipped", "No DMA name extracted from zip report")
            return {}
        try:
            result = await query_google_trends(dma_name)
            data = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
            top_ct = len(data.get("topTerms", []))
            rising_ct = len(data.get("risingTerms", []))
            if top_ct or rising_ct:
                _record("google_trends", "ok",
                        f"DMA '{dma_name}': {top_ct} top, {rising_ct} rising terms",
                        {"topTerms": data.get("topTerms", [])[:5], "risingTerms": data.get("risingTerms", [])[:5]})
            else:
                _record("google_trends", "empty", f"No trends for DMA '{dma_name}'")
            return data
        except Exception as e:
            _record("google_trends", "error", str(e))
            return {}

    async def _fetch_catalysts() -> dict[str, Any]:
        loc_city = city if city and city != zip_code else ""
        if not loc_city:
            _record("local_catalysts", "skipped", "No city name available for catalyst search")
            return {}
        loc_state = state or "NJ"
        try:
            result = await research_local_catalysts(loc_city, loc_state, business_type)
            catalyst_count = len(result.get("catalysts", []))
            if catalyst_count > 0:
                _record("local_catalysts", "ok", f"{catalyst_count} catalysts found",
                        {"summary": result.get("summary", "")})
            else:
                _record("local_catalysts", "empty", result.get("summary", "No catalysts found"))
            return result
        except Exception as e:
            _record("local_catalysts", "error", str(e))
            return {}

    async def _fetch_legal_notices() -> dict[str, Any]:
        # Only for NJ zip codes (or states with known legal notice portals)
        if state and state.upper() not in ("NJ", "NEW JERSEY"):
            _record("legal_notices", "skipped", f"Legal notice scraping not available for {state}")
            return {}
        loc_city = city if city and city != zip_code else ""
        if not loc_city:
            _record("legal_notices", "skipped", "No city name available")
            return {}
        try:
            from hephae_integrations.nj_legal_notices_client import query_legal_notices
            result = await query_legal_notices(loc_city, "NJ", zip_code)
            notice_count = len(result.get("notices", []))
            if notice_count > 0:
                _record("legal_notices", "ok", f"{notice_count} notices found",
                        {"summary": result.get("summary", "")})
            else:
                _record("legal_notices", "empty", "No relevant notices found")
            return result
        except ImportError:
            _record("legal_notices", "skipped", "nj_legal_notices_client not installed")
            return {}
        except Exception as e:
            _record("legal_notices", "error", str(e))
            return {}

    # Run ALL fetchers in parallel
    weather, industry_data, news_data, trends_data, catalyst_data, legal_data = await asyncio.gather(
        _fetch_weather(),
        _fetch_industry(),
        _fetch_news(),
        _fetch_trends(),
        _fetch_catalysts(),
        _fetch_legal_notices(),
    )

    # Merge results
    if weather and weather.get("forecast"):
        signals["weather"] = weather
        signals_used.append("weather_nws")

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

    if legal_data and legal_data.get("notices"):
        signals["legalNotices"] = legal_data
        signals_used.append("legal_notices")

    # ── 8. Prior week's pulse ────────────────────────────────────────
    prior_pulse = None
    try:
        prior = await get_latest_pulse(zip_code, business_type)
        if prior and prior.get("weekOf") != week_of:
            prior_pulse = prior
            _record("prior_pulse", "ok", f"Found prior pulse from {prior.get('weekOf', '?')}")
        else:
            _record("prior_pulse", "skipped", "No prior pulse available")
    except Exception:
        _record("prior_pulse", "skipped", "Could not load prior pulse")

    # ── 9. Run WeeklyPulseAgent ──────────────────────────────────────
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

    # ── 10. Save ─────────────────────────────────────────────────────
    pulse_id = await save_weekly_pulse(
        zip_code=zip_code,
        business_type=business_type,
        week_of=week_of,
        pulse=pulse,
        signals_used=signals_used,
        diagnostics=diagnostics,
    )

    logger.info(f"[WeeklyPulse] Pulse saved as {pulse_id} with {len(pulse.get('insights', []))} insights from {len(signals_used)} signals")

    return {
        "pulse": pulse,
        "pulseId": pulse_id,
        "signalsUsed": signals_used,
        "diagnostics": diagnostics,
    }
