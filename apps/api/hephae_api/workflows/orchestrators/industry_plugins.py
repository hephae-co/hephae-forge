"""Industry plugin registry — maps business types to data fetcher functions.

Architecture: BQ-first with API fallback.

BigQuery public datasets (free, no keys, always available):
- census_bureau_acs → demographics, income, poverty, housing (replaces SchoolDigger)
- geo_openstreetmap → business density, competition count (replaces Yelp)
- noaa_gsod → historical weather patterns (supplements NWS forecast)
- utility_us.zipcode_area → geography bridging (zip → lat/lon/county)

API sources (some free, some need keys):
- BLS CPI v1 (no key) / v2 (with key) → food price indexes
- USDA NASS (needs key) → agricultural commodity prices
- FDA (free) → food safety recalls
- SBA (free) → business formation signals
- Yelp Fusion (needs key) → ratings, reviews (supplements OSM counts)
- NWS (free) → 7-day forecast
"""

from __future__ import annotations

import asyncio
import os
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Business type classification
# ---------------------------------------------------------------------------

FOOD_TYPES = {
    "restaurants", "restaurant", "bakeries", "bakery", "cafes", "cafe",
    "coffee shops", "coffee", "pizza", "pizzeria", "tacos", "taqueria",
    "delis", "deli", "ice cream", "gelato", "juice bar", "smoothie",
    "seafood", "fish market", "butcher", "grocery", "supermarket",
}

RETAIL_TYPES = {
    "retail", "clothing", "boutique", "gift shop", "hardware",
    "electronics", "bookstore", "pet store", "florist",
}

BEAUTY_TYPES = {
    "salons", "salon", "spas", "spa", "barbers", "barber",
    "nail salon", "beauty", "wellness",
}

SERVICE_TYPES = {
    "auto repair", "laundry", "dry cleaning", "fitness", "gym",
    "tutoring", "daycare", "veterinary", "vet",
}


def _matches(business_type: str, type_set: set[str]) -> bool:
    normalized = business_type.lower().strip()
    return normalized in type_set or any(t in normalized for t in type_set)


def is_food_business(business_type: str) -> bool:
    return _matches(business_type, FOOD_TYPES)


async def fetch_industry_data(
    business_type: str,
    state: str = "",
    zip_code: str = "",
    county: str = "",
    latitude: float = 0.0,
    longitude: float = 0.0,
) -> dict[str, Any]:
    """Fetch all relevant data sources for a business type.

    BQ sources run unconditionally (free, reliable).
    API sources run conditionally (based on key availability + business type).
    """
    data: dict[str, Any] = {}

    # ── BQ sources (always available, run in parallel) ───────────────
    bq_tasks: list[tuple[str, Any]] = []

    # Census demographics (replaces SchoolDigger)
    if zip_code:
        bq_tasks.append(("censusDemographics", _fetch_census(zip_code)))

    # OSM business density (replaces Yelp for counts)
    if latitude and longitude:
        bq_tasks.append(("osmDensity", _fetch_osm(latitude, longitude, business_type)))

    # NOAA historical weather
    if latitude and longitude:
        bq_tasks.append(("weatherHistory", _fetch_noaa(latitude, longitude)))

    # ── API sources (conditional on keys + business type) ────────────
    api_tasks: list[tuple[str, Any]] = []

    # BLS CPI — always try (v1 needs no key)
    if _matches(business_type, FOOD_TYPES | RETAIL_TYPES | BEAUTY_TYPES | SERVICE_TYPES):
        api_tasks.append(("blsCpi", _fetch_bls(business_type)))

    # Food-specific APIs
    if _matches(business_type, FOOD_TYPES):
        api_tasks.append(("fdaRecalls", _fetch_fda(state)))
        api_tasks.append(("usdaPrices", _fetch_usda(business_type, state)))
        if os.getenv("USDA_FDC_API_KEY"):
            api_tasks.append(("usdaFoodData", _fetch_usda_fdc(business_type)))

    # SBA loans (free, no key)
    if zip_code:
        api_tasks.append(("sbaLoans", _fetch_sba(zip_code)))

    # CDC PLACES health metrics (free, no key, ZIP-level)
    if zip_code:
        api_tasks.append(("healthMetrics", _fetch_cdc_places(zip_code)))

    # FHFA House Price Index (free, ZIP-level)
    if zip_code:
        api_tasks.append(("housePriceIndex", _fetch_fhfa_hpi(zip_code)))

    # IRS SOI income data (free, ZIP-level)
    if zip_code:
        api_tasks.append(("irsIncome", _fetch_irs_income(zip_code)))

    # BLS QCEW employment data (free, county-level)
    if county and state:
        api_tasks.append(("qcewEmployment", _fetch_qcew(county, state, business_type)))

    # Yelp (supplements OSM with ratings/reviews — only if key present)
    if zip_code and os.getenv("YELP_API_KEY"):
        api_tasks.append(("yelpData", _fetch_yelp(zip_code, business_type)))

    # Run all in parallel
    all_tasks = bq_tasks + api_tasks
    if not all_tasks:
        return data

    labels = [t[0] for t in all_tasks]
    coros = [t[1] for t in all_tasks]
    results = await asyncio.gather(*coros, return_exceptions=True)

    for label, result in zip(labels, results):
        if isinstance(result, Exception):
            logger.error(f"[IndustryPlugins] {label} failed: {result}")
        elif result:
            data[label] = result
            # Add computed deltas for BLS data
            if label == "blsCpi" and result.get("series"):
                from hephae_integrations.bls_client import compute_price_deltas
                data["priceDeltas"] = compute_price_deltas(result["series"])
            logger.info(f"[IndustryPlugins] {label} complete")

    return data


# ── BQ fetch wrappers ────────────────────────────────────────────────────

async def _fetch_census(zip_code: str) -> dict[str, Any]:
    from hephae_db.bigquery.public_data import query_census_demographics
    return await query_census_demographics(zip_code)


async def _fetch_osm(lat: float, lon: float, business_type: str) -> dict[str, Any]:
    from hephae_db.bigquery.public_data import query_osm_business_density
    return await query_osm_business_density(lat, lon, business_type)


async def _fetch_noaa(lat: float, lon: float) -> dict[str, Any]:
    from hephae_db.bigquery.public_data import query_noaa_weather_history
    return await query_noaa_weather_history(lat, lon)


# ── API fetch wrappers ───────────────────────────────────────────────────

async def _fetch_bls(business_type: str) -> dict[str, Any]:
    from hephae_integrations.bls_client import query_bls_cpi
    return await query_bls_cpi(business_type)


async def _fetch_fda(state: str) -> dict[str, Any]:
    from hephae_integrations.fda_client import query_fda_enforcements
    return await query_fda_enforcements(state)


async def _fetch_usda(business_type: str, state: str) -> dict[str, Any]:
    from hephae_integrations.usda_client import query_usda_prices
    return await query_usda_prices(business_type, state)


async def _fetch_sba(zip_code: str) -> dict[str, Any]:
    from hephae_integrations.sba_client import query_sba_loans
    return await query_sba_loans(zip_code)


async def _fetch_yelp(zip_code: str, business_type: str) -> dict[str, Any]:
    from hephae_integrations.yelp_client import query_yelp_businesses
    return await query_yelp_businesses(zip_code, business_type)


async def _fetch_usda_fdc(business_type: str) -> dict[str, Any]:
    from hephae_integrations.usda_fdc_client import query_fdc_food_prices
    return await query_fdc_food_prices(business_type)


async def _fetch_cdc_places(zip_code: str) -> dict[str, Any]:
    from hephae_integrations.cdc_places_client import query_health_metrics
    return await query_health_metrics(zip_code)


async def _fetch_fhfa_hpi(zip_code: str) -> dict[str, Any]:
    from hephae_integrations.fhfa_hpi_client import query_house_price_index
    return await query_house_price_index(zip_code)


async def _fetch_irs_income(zip_code: str) -> dict[str, Any]:
    try:
        from hephae_integrations.irs_soi_client import query_zip_income
        return await query_zip_income(zip_code)
    except ImportError:
        return {}


async def _fetch_qcew(county: str, state: str, business_type: str) -> dict[str, Any]:
    from hephae_integrations.bls_qcew_client import query_qcew_employment
    return await query_qcew_employment(county, state, business_type)
