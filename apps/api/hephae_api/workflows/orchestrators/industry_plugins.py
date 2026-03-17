"""Industry plugin registry — maps business types to data fetcher functions.

Each plugin defines which external data sources are relevant for a business type.
The weekly pulse orchestrator uses this to conditionally fetch industry-specific data.

Data sources:
- BLS CPI (food price indexes — v1 no key, v2 with key)
- USDA NASS (agricultural commodity prices)
- FDA (food safety recalls)
- Yelp Fusion (competition density, ratings, new entrants)
- SBA loans (new business entry signals)
- EIA (energy costs — state level, all business types)
- FBI UCR (crime/safety — county level)
- SchoolDigger (education/economic stress proxy)
"""

from __future__ import annotations

import asyncio
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


def get_industry_plugins(business_type: str) -> list[str]:
    """Return list of data source keys relevant for a business type.

    Base layer (all types): yelp, sba_loans, energy, crime, education
    Food layer: + bls_cpi, usda_prices, fda_recalls
    """
    plugins: list[str] = []

    # Base layer — every business type gets these
    plugins.extend(["yelp", "sba_loans", "energy", "crime", "education"])

    # Food-specific
    if _matches(business_type, FOOD_TYPES):
        plugins.extend(["bls_cpi", "usda_prices", "fda_recalls"])
    # Retail gets BLS for consumer price context
    elif _matches(business_type, RETAIL_TYPES):
        plugins.append("bls_cpi")
    # Beauty/services get BLS for service price context
    elif _matches(business_type, BEAUTY_TYPES | SERVICE_TYPES):
        plugins.append("bls_cpi")

    return plugins


async def fetch_industry_data(
    business_type: str,
    state: str = "",
    zip_code: str = "",
    county: str = "",
) -> dict[str, Any]:
    """Fetch all relevant industry data sources for a business type.

    Returns dict with source-keyed results. Failed sources are omitted.
    Each successful source includes its data.
    """
    from hephae_integrations.bls_client import query_bls_cpi, compute_price_deltas
    from hephae_integrations.usda_client import query_usda_prices
    from hephae_integrations.fda_client import query_fda_enforcements

    plugins = get_industry_plugins(business_type)
    if not plugins:
        return {}

    tasks: list[tuple[str, Any]] = []

    for plugin in plugins:
        if plugin == "bls_cpi":
            tasks.append(("blsCpi", query_bls_cpi(business_type)))
        elif plugin == "usda_prices":
            tasks.append(("usdaPrices", query_usda_prices(business_type, state)))
        elif plugin == "fda_recalls":
            tasks.append(("fdaRecalls", query_fda_enforcements(state)))
        elif plugin == "yelp":
            try:
                from hephae_integrations.yelp_client import query_yelp_businesses
                if zip_code:
                    tasks.append(("yelpData", query_yelp_businesses(zip_code, business_type)))
            except ImportError:
                logger.debug("[IndustryPlugins] yelp_client not available")
        elif plugin == "sba_loans":
            try:
                from hephae_integrations.sba_client import query_sba_loans
                if zip_code:
                    tasks.append(("sbaLoans", query_sba_loans(zip_code)))
            except ImportError:
                logger.debug("[IndustryPlugins] sba_client not available")
        elif plugin == "energy":
            try:
                from hephae_integrations.eia_client import query_energy_costs
                if state:
                    tasks.append(("energyCosts", query_energy_costs(state)))
            except ImportError:
                logger.debug("[IndustryPlugins] eia_client not available")
        elif plugin == "crime":
            try:
                from hephae_integrations.fbi_ucr_client import query_crime_stats
                if state:
                    tasks.append(("crimeStats", query_crime_stats(state, county)))
            except ImportError:
                logger.debug("[IndustryPlugins] fbi_ucr_client not available")
        elif plugin == "education":
            try:
                from hephae_integrations.schooldigger_client import query_school_data
                if zip_code:
                    tasks.append(("educationData", query_school_data(zip_code)))
            except ImportError:
                logger.debug("[IndustryPlugins] schooldigger_client not available")

    if not tasks:
        return {}

    labels = [t[0] for t in tasks]
    coros = [t[1] for t in tasks]
    results = await asyncio.gather(*coros, return_exceptions=True)

    data: dict[str, Any] = {}
    for label, result in zip(labels, results):
        if isinstance(result, Exception):
            logger.error(f"[IndustryPlugins] {label} failed: {result}")
        elif result:
            data[label] = result
            # Add computed deltas for BLS data
            if label == "blsCpi" and result.get("series"):
                data["priceDeltas"] = compute_price_deltas(result["series"])
            logger.info(f"[IndustryPlugins] {label} complete")

    return data
