"""Pulse signal fetch tools — cache-through wrappers for all data sources.

Each fetch function follows the pattern:
  1. Check data_cache for a hit
  2. If hit, return cached data
  3. If miss, call the real API/BQ source
  4. Store result in cache with appropriate TTL
  5. Return result

These are used by Stage 1 (DataGatherer) of the pulse pipeline.
They are plain async functions, NOT ADK tools — called deterministically
from custom BaseAgent subclasses (no LLM dispatch).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

from hephae_db.firestore.data_cache import (
    TTL_SHARED,
    TTL_STATIC,
    TTL_WEEKLY,
    get_cached,
    set_cached,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# BQ sources (free, always available) — TTL_STATIC (90 days)
# ---------------------------------------------------------------------------


async def fetch_census(zip_code: str) -> dict[str, Any]:
    """Census ACS demographics for a zip code."""
    cached = await get_cached("census", zip_code)
    if cached:
        return cached
    from hephae_db.bigquery.public_data import query_census_demographics
    result = await query_census_demographics(zip_code)
    if result:
        await set_cached("census", zip_code, result, TTL_STATIC)
    return result or {}


async def fetch_osm(latitude: float, longitude: float, business_type: str) -> dict[str, Any]:
    """OpenStreetMap business density around a point."""
    scope_key = f"{latitude:.4f},{longitude:.4f}:{business_type}"
    cached = await get_cached("osm", scope_key)
    if cached:
        return cached
    from hephae_db.bigquery.public_data import query_osm_business_density
    result = await query_osm_business_density(latitude, longitude, business_type)
    if result:
        await set_cached("osm", scope_key, result, TTL_STATIC)
    return result or {}


async def fetch_noaa(latitude: float, longitude: float) -> dict[str, Any]:
    """NOAA historical weather baseline (5-year average)."""
    scope_key = f"{latitude:.4f},{longitude:.4f}"
    cached = await get_cached("noaa", scope_key)
    if cached:
        return cached
    from hephae_db.bigquery.public_data import query_noaa_weather_history
    result = await query_noaa_weather_history(latitude, longitude)
    if result:
        await set_cached("noaa", scope_key, result, TTL_STATIC)
    return result or {}


# ---------------------------------------------------------------------------
# Weekly sources — TTL_WEEKLY (7 days)
# ---------------------------------------------------------------------------


async def fetch_weather(zip_code: str) -> dict[str, Any]:
    """NWS 7-day weather forecast."""
    cached = await get_cached("weather", zip_code)
    if cached:
        return cached
    try:
        from hephae_integrations.nws_client import query_weather_forecast
        result = await query_weather_forecast(zip_code)
        if result and result.get("forecast"):
            await set_cached("weather", zip_code, result, TTL_WEEKLY)
            return result
    except ImportError:
        pass
    return {}


async def fetch_news(city: str, state: str, business_type: str) -> dict[str, Any]:
    """Local news via Google News RSS."""
    location = f"{city}, {state}" if city and state else city
    if not location:
        return {}
    scope_key = f"{location}:{business_type}"
    cached = await get_cached("news", scope_key)
    if cached:
        return cached
    from hephae_integrations.news_client import query_local_news
    result = await query_local_news(location, business_type)
    if result and result.get("articles"):
        await set_cached("news", scope_key, result, TTL_WEEKLY)
    return result or {}


async def fetch_trends(dma_name: str) -> dict[str, Any]:
    """Google Trends via BigQuery DMA data."""
    if not dma_name:
        return {}
    cached = await get_cached("trends", dma_name)
    if cached:
        return cached
    from hephae_db.bigquery.reader import query_google_trends
    result = await query_google_trends(dma_name)
    data = result.model_dump(mode="json") if hasattr(result, "model_dump") else (result or {})
    if data:
        await set_cached("trends", dma_name, data, TTL_WEEKLY)
    return data


async def fetch_bls_cpi(business_type: str) -> dict[str, Any]:
    """BLS Consumer Price Index data."""
    cached = await get_cached("blsCpi", business_type)
    if cached:
        return cached
    from hephae_integrations.bls_client import query_bls_cpi
    result = await query_bls_cpi(business_type)
    if result:
        await set_cached("blsCpi", business_type, result, TTL_WEEKLY)
    return result or {}


async def fetch_sba(zip_code: str) -> dict[str, Any]:
    """SBA loan data (business formation signals)."""
    cached = await get_cached("sba", zip_code)
    if cached:
        return cached
    from hephae_integrations.sba_client import query_sba_loans
    result = await query_sba_loans(zip_code)
    if result:
        await set_cached("sba", zip_code, result, TTL_WEEKLY)
    return result or {}


async def fetch_legal_notices(city: str, state: str, zip_code: str) -> dict[str, Any]:
    """NJ legal notices (only for NJ zips)."""
    if not state or state.upper() not in ("NJ", "NEW JERSEY"):
        return {}
    if not city or city == zip_code:
        return {}
    scope_key = f"{city}:{state}:{zip_code}"
    cached = await get_cached("legal", scope_key)
    if cached:
        return cached
    try:
        from hephae_integrations.nj_legal_notices_client import query_legal_notices
        result = await query_legal_notices(city, "NJ", zip_code)
        if result and result.get("notices"):
            await set_cached("legal", scope_key, result, TTL_WEEKLY)
            return result
    except ImportError:
        pass
    return {}


# ---------------------------------------------------------------------------
# Shared sources (county/state scope) — TTL_SHARED (30 days)
# ---------------------------------------------------------------------------


async def fetch_fda(state: str) -> dict[str, Any]:
    """FDA food safety recalls (state-level)."""
    if not state:
        return {}
    cached = await get_cached("fda", state)
    if cached:
        return cached
    from hephae_integrations.fda_client import query_fda_enforcements
    result = await query_fda_enforcements(state)
    if result:
        await set_cached("fda", state, result, TTL_SHARED)
    return result or {}


async def fetch_usda(business_type: str, state: str) -> dict[str, Any]:
    """USDA commodity prices."""
    scope_key = f"{business_type}:{state}"
    cached = await get_cached("usda", scope_key)
    if cached:
        return cached
    from hephae_integrations.usda_client import query_usda_prices
    result = await query_usda_prices(business_type, state)
    if result:
        await set_cached("usda", scope_key, result, TTL_SHARED)
    return result or {}


async def fetch_qcew(county: str, state: str, business_type: str) -> dict[str, Any]:
    """BLS QCEW employment data (county-level)."""
    scope_key = f"{county}:{state}:{business_type}"
    cached = await get_cached("qcew", scope_key)
    if cached:
        return cached
    from hephae_integrations.bls_qcew_client import query_qcew_employment
    result = await query_qcew_employment(county, state, business_type)
    if result:
        await set_cached("qcew", scope_key, result, TTL_SHARED)
    return result or {}


# ---------------------------------------------------------------------------
# Static sources — TTL_STATIC (90 days)
# ---------------------------------------------------------------------------


async def fetch_cdc_places(zip_code: str) -> dict[str, Any]:
    """CDC PLACES health metrics (ZIP-level)."""
    cached = await get_cached("cdcPlaces", zip_code)
    if cached:
        return cached
    from hephae_integrations.cdc_places_client import query_health_metrics
    result = await query_health_metrics(zip_code)
    if result:
        await set_cached("cdcPlaces", zip_code, result, TTL_STATIC)
    return result or {}


async def fetch_fhfa_hpi(zip_code: str) -> dict[str, Any]:
    """FHFA House Price Index (ZIP-level)."""
    cached = await get_cached("fhfa", zip_code)
    if cached:
        return cached
    from hephae_integrations.fhfa_hpi_client import query_house_price_index
    result = await query_house_price_index(zip_code)
    if result:
        await set_cached("fhfa", zip_code, result, TTL_STATIC)
    return result or {}


async def fetch_irs_income(zip_code: str) -> dict[str, Any]:
    """IRS SOI income data (ZIP-level)."""
    cached = await get_cached("irs", zip_code)
    if cached:
        return cached
    try:
        from hephae_integrations.irs_soi_client import query_zip_income
        result = await query_zip_income(zip_code)
        if result:
            await set_cached("irs", zip_code, result, TTL_STATIC)
        return result or {}
    except ImportError:
        return {}


async def fetch_yelp(zip_code: str, business_type: str) -> dict[str, Any]:
    """Yelp Fusion data (only if API key present)."""
    if not os.getenv("YELP_API_KEY"):
        return {}
    scope_key = f"{zip_code}:{business_type}"
    cached = await get_cached("yelp", scope_key)
    if cached:
        return cached
    from hephae_integrations.yelp_client import query_yelp_businesses
    result = await query_yelp_businesses(zip_code, business_type)
    if result:
        await set_cached("yelp", scope_key, result, TTL_WEEKLY)
    return result or {}


# ---------------------------------------------------------------------------
# National signals — same for all zips in an industry (BLS, USDA, FDA)
# ---------------------------------------------------------------------------


async def fetch_national_signals(
    business_type: str,
    state: str = "",
) -> dict[str, Any]:
    """Fetch industry-wide national signals (BLS CPI, USDA, FDA, price deltas).

    These are the same for every zip code in the same industry.
    Called once per industry per week by the industry pulse cron.
    """
    import asyncio
    from hephae_api.workflows.orchestrators.industry_plugins import is_food_business

    is_food = is_food_business(business_type)

    tasks: list[tuple[str, Any]] = []
    tasks.append(("blsCpi", fetch_bls_cpi(business_type)))
    if is_food:
        tasks.append(("fdaRecalls", fetch_fda(state)))
        tasks.append(("usdaPrices", fetch_usda(business_type, state)))

    labels = [t[0] for t in tasks]
    coros = [t[1] for t in tasks]
    results = await asyncio.gather(*coros, return_exceptions=True)

    signals: dict[str, Any] = {}
    for label, result in zip(labels, results):
        if isinstance(result, Exception):
            logger.error(f"[PulseFetch] national {label} failed: {result}")
        elif result:
            signals[label] = result

    # Compute price deltas from BLS data
    if signals.get("blsCpi") and signals["blsCpi"].get("series"):
        try:
            from hephae_integrations.bls_client import compute_price_deltas
            signals["priceDeltas"] = compute_price_deltas(signals["blsCpi"]["series"])
        except Exception as e:
            logger.warning(f"[PulseFetch] Price delta computation failed: {e}")

    return signals


# ---------------------------------------------------------------------------
# Local signals — zip-specific (census, weather, news, trends, etc.)
# ---------------------------------------------------------------------------


async def fetch_local_signals(
    zip_code: str,
    business_type: str,
    city: str,
    state: str,
    county: str,
    latitude: float,
    longitude: float,
    dma_name: str,
) -> dict[str, Any]:
    """Fetch zip-specific local signals.

    Census, OSM, weather, news, trends, SBA, QCEW, IRS, health, FHFA, Yelp.
    Called per zip code by the zip pulse cron.
    """
    import asyncio

    tasks: list[tuple[str, Any]] = []

    if zip_code:
        tasks.append(("censusDemographics", fetch_census(zip_code)))
    if latitude and longitude:
        tasks.append(("osmDensity", fetch_osm(latitude, longitude, business_type)))
        tasks.append(("weatherHistory", fetch_noaa(latitude, longitude)))

    tasks.append(("weather", fetch_weather(zip_code)))
    tasks.append(("localNews", fetch_news(city, state, business_type)))
    tasks.append(("trends", fetch_trends(dma_name)))
    tasks.append(("legalNotices", fetch_legal_notices(city, state, zip_code)))
    tasks.append(("sbaLoans", fetch_sba(zip_code)))

    if zip_code:
        tasks.append(("healthMetrics", fetch_cdc_places(zip_code)))
        tasks.append(("housePriceIndex", fetch_fhfa_hpi(zip_code)))
        tasks.append(("irsIncome", fetch_irs_income(zip_code)))
    if county and state:
        tasks.append(("qcewEmployment", fetch_qcew(county, state, business_type)))

    tasks.append(("yelpData", fetch_yelp(zip_code, business_type)))

    labels = [t[0] for t in tasks]
    coros = [t[1] for t in tasks]
    results = await asyncio.gather(*coros, return_exceptions=True)

    signals: dict[str, Any] = {}
    for label, result in zip(labels, results):
        if isinstance(result, Exception):
            logger.error(f"[PulseFetch] local {label} failed: {result}")
        elif result:
            signals[label] = result

    return signals


# ---------------------------------------------------------------------------
# Aggregate fetcher — backward-compatible wrapper
# ---------------------------------------------------------------------------


async def fetch_all_signals(
    zip_code: str,
    business_type: str,
    city: str,
    state: str,
    county: str,
    latitude: float,
    longitude: float,
    dma_name: str,
) -> dict[str, Any]:
    """Fetch all data signals for a zip code, returning a flat dict of source → data.

    Backward-compatible wrapper: calls fetch_national_signals() + fetch_local_signals()
    and merges the results. Existing callers don't need to change.
    """
    import asyncio

    national, local = await asyncio.gather(
        fetch_national_signals(business_type, state),
        fetch_local_signals(
            zip_code, business_type, city, state,
            county, latitude, longitude, dma_name,
        ),
    )
    return {**national, **local}
