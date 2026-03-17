"""Industry plugin registry — maps business types to data fetcher functions.

Each plugin defines which external data sources are relevant for a business type.
The weekly pulse orchestrator uses this to conditionally fetch industry-specific data.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Plugin definitions: business type → list of data source keys
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


def get_industry_plugins(business_type: str) -> list[str]:
    """Return list of data source keys for a business type.

    Possible keys: "bls_cpi", "usda_prices", "fda_recalls", "consumer_spending"
    """
    normalized = business_type.lower().strip()
    plugins: list[str] = []

    if normalized in FOOD_TYPES or any(ft in normalized for ft in FOOD_TYPES):
        plugins.extend(["bls_cpi", "usda_prices", "fda_recalls"])
    elif normalized in RETAIL_TYPES or any(rt in normalized for rt in RETAIL_TYPES):
        plugins.append("bls_cpi")
    elif normalized in BEAUTY_TYPES or any(bt in normalized for bt in BEAUTY_TYPES):
        plugins.append("bls_cpi")

    return plugins


def is_food_business(business_type: str) -> bool:
    """Check if a business type is food-related."""
    normalized = business_type.lower().strip()
    return normalized in FOOD_TYPES or any(ft in normalized for ft in FOOD_TYPES)


async def fetch_industry_data(
    business_type: str,
    state: str = "",
) -> dict[str, Any]:
    """Fetch all relevant industry data sources for a business type.

    Returns dict with keys like "blsCpi", "usdaPrices", "fdaRecalls"
    containing the raw data from each source. Failed sources are omitted.
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
