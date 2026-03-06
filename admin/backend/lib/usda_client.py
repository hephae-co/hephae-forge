"""USDA NASS QuickStats API client for agricultural commodity prices."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.config import settings
from backend.lib.db.food_prices import get_cached_food_prices, save_food_prices_cache
from backend.types import UsdaCommodityPrice, UsdaPriceData

logger = logging.getLogger(__name__)

NASS_API_URL = "https://quickstats.nass.usda.gov/api/api_GET/"

# Commodities relevant to food-related businesses, grouped by industry
INDUSTRY_COMMODITIES: dict[str, list[dict[str, str]]] = {
    "bakeries": [
        {"commodity_desc": "WHEAT", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "EGGS", "statisticcat_desc": "PRICE RECEIVED"},
    ],
    "restaurants": [
        {"commodity_desc": "CATTLE", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "HOGS", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "CHICKENS", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "EGGS", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "MILK", "statisticcat_desc": "PRICE RECEIVED"},
    ],
    "pizza": [
        {"commodity_desc": "WHEAT", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "MILK", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "HOGS", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "TOMATOES", "statisticcat_desc": "PRICE RECEIVED"},
    ],
    "coffee": [
        {"commodity_desc": "MILK", "statisticcat_desc": "PRICE RECEIVED"},
    ],
    "ice cream": [
        {"commodity_desc": "MILK", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "EGGS", "statisticcat_desc": "PRICE RECEIVED"},
    ],
    "tacos": [
        {"commodity_desc": "CATTLE", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "HOGS", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "TOMATOES", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "ONIONS", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "PEPPERS", "statisticcat_desc": "PRICE RECEIVED"},
    ],
    "seafood": [
        # NASS has limited seafood — mostly through NOAA, not USDA
        {"commodity_desc": "CATFISH", "statisticcat_desc": "PRICE RECEIVED"},
    ],
    "butcher": [
        {"commodity_desc": "CATTLE", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "HOGS", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "CHICKENS", "statisticcat_desc": "PRICE RECEIVED"},
    ],
    "grocery": [
        {"commodity_desc": "CATTLE", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "HOGS", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "MILK", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "EGGS", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "WHEAT", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "CORN", "statisticcat_desc": "PRICE RECEIVED"},
    ],
    "juice bar": [
        {"commodity_desc": "ORANGES", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "APPLES", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "STRAWBERRIES", "statisticcat_desc": "PRICE RECEIVED"},
    ],
    "deli": [
        {"commodity_desc": "HOGS", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "CATTLE", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "MILK", "statisticcat_desc": "PRICE RECEIVED"},
        {"commodity_desc": "WHEAT", "statisticcat_desc": "PRICE RECEIVED"},
    ],
}

# Default commodities for any food-related business
DEFAULT_FOOD_COMMODITIES: list[dict[str, str]] = [
    {"commodity_desc": "CATTLE", "statisticcat_desc": "PRICE RECEIVED"},
    {"commodity_desc": "MILK", "statisticcat_desc": "PRICE RECEIVED"},
    {"commodity_desc": "EGGS", "statisticcat_desc": "PRICE RECEIVED"},
    {"commodity_desc": "WHEAT", "statisticcat_desc": "PRICE RECEIVED"},
]


def _get_commodities_for_industry(industry: str) -> list[dict[str, str]]:
    """Get the relevant commodity queries for a given business type."""
    normalized = industry.lower().strip()

    # Direct match
    if normalized in INDUSTRY_COMMODITIES:
        return INDUSTRY_COMMODITIES[normalized]

    # Try without trailing 's'
    singular = normalized.rstrip("s")
    if singular in INDUSTRY_COMMODITIES:
        return INDUSTRY_COMMODITIES[singular]

    # Partial match
    for key in INDUSTRY_COMMODITIES:
        if key in normalized or normalized in key:
            return INDUSTRY_COMMODITIES[key]

    return DEFAULT_FOOD_COMMODITIES


async def _fetch_commodity(
    client: httpx.AsyncClient,
    api_key: str,
    commodity: str,
    stat_cat: str,
    state: str = "",
    year_start: int = 0,
) -> list[dict[str, Any]]:
    """Fetch price data for a single commodity from NASS QuickStats."""
    params: dict[str, str] = {
        "key": api_key,
        "source_desc": "SURVEY",
        "statisticcat_desc": stat_cat,
        "commodity_desc": commodity,
        "agg_level_desc": "NATIONAL" if not state else "STATE",
        "freq_desc": "ANNUAL",
        "format": "JSON",
    }

    if state:
        state_upper = state.upper()
        if len(state_upper) == 2:
            params["state_alpha"] = state_upper
        else:
            params["state_name"] = state_upper

    if year_start:
        params["year__GE"] = str(year_start)

    try:
        response = await client.get(NASS_API_URL, params=params)

        if response.status_code == 400:
            # Often means "exceeds limit" or bad params — not fatal
            logger.debug(f"[USDA] 400 for {commodity}: {response.text[:200]}")
            return []
        if response.status_code != 200:
            logger.warning(f"[USDA] API returned {response.status_code} for {commodity}")
            return []

        data = response.json()
        return data.get("data", [])

    except Exception as e:
        logger.error(f"[USDA] Fetch failed for {commodity}: {e}")
        return []


def _parse_records(records: list[dict[str, Any]]) -> list[UsdaCommodityPrice]:
    """Parse NASS API records into our model."""
    prices: list[UsdaCommodityPrice] = []

    for r in records:
        value_str = r.get("Value", "").strip().replace(",", "")
        if not value_str or value_str in ("(D)", "(NA)", "(Z)", "(S)"):
            continue  # withheld/not available

        try:
            value = float(value_str)
        except ValueError:
            continue

        prices.append(UsdaCommodityPrice(
            commodity=r.get("commodity_desc", ""),
            year=int(r.get("year", 0)),
            period=r.get("reference_period_desc", r.get("freq_desc", "")),
            value=value,
            unit=r.get("unit_desc", ""),
            state=r.get("state_name", r.get("state_alpha", "US")),
        ))

    prices.sort(key=lambda p: (p.commodity, p.year))
    return prices


def _generate_highlights(prices: list[UsdaCommodityPrice]) -> list[str]:
    """Generate human-readable highlights from price data."""
    highlights: list[str] = []

    # Group by commodity
    by_commodity: dict[str, list[UsdaCommodityPrice]] = {}
    for p in prices:
        by_commodity.setdefault(p.commodity, []).append(p)

    for commodity, records in by_commodity.items():
        records.sort(key=lambda r: r.year)
        if len(records) < 2:
            if records:
                r = records[-1]
                highlights.append(f"{commodity}: ${r.value:.2f}/{r.unit} ({r.year})")
            continue

        latest = records[-1]
        prev = records[-2]

        if prev.value > 0:
            pct_change = ((latest.value - prev.value) / prev.value) * 100
            direction = "up" if pct_change > 0 else "down"
            highlights.append(
                f"{commodity}: ${latest.value:.2f}/{latest.unit} ({latest.year}), "
                f"{abs(pct_change):.1f}% {direction} from {prev.year}"
            )
        else:
            highlights.append(f"{commodity}: ${latest.value:.2f}/{latest.unit} ({latest.year})")

    return highlights


async def query_usda_prices(industry: str, state: str = "") -> UsdaPriceData:
    """Query USDA NASS for agricultural commodity prices relevant to an industry.

    Args:
        industry: Business type (e.g., "bakeries", "pizza", "restaurants").
        state: Optional state name or 2-letter abbreviation for state-level data.
               If empty, returns national data.

    Returns:
        UsdaPriceData with commodity prices and highlights.
    """
    empty = UsdaPriceData()

    api_key = settings.USDA_NASS_API_KEY
    if not api_key:
        logger.warning("[USDA] No USDA_NASS_API_KEY configured — skipping NASS query")
        return empty

    # Cache-first: check Firestore for recent data
    try:
        cached = await get_cached_food_prices("usda", industry, state)
        if cached:
            return UsdaPriceData.model_validate(cached)
    except Exception:
        pass

    try:
        commodities = _get_commodities_for_industry(industry)
        if not commodities:
            return empty

        from datetime import datetime
        year_start = datetime.utcnow().year - 3  # last 3 years

        logger.info(
            f"[USDA] Querying {len(commodities)} commodities for "
            f"industry={industry}, state={state or 'national'}"
        )

        all_prices: list[UsdaCommodityPrice] = []

        async with httpx.AsyncClient(timeout=30) as client:
            for commodity_params in commodities:
                records = await _fetch_commodity(
                    client=client,
                    api_key=api_key,
                    commodity=commodity_params["commodity_desc"],
                    stat_cat=commodity_params["statisticcat_desc"],
                    state=state,
                    year_start=year_start,
                )
                all_prices.extend(_parse_records(records))

        highlights = _generate_highlights(all_prices)

        logger.info(f"[USDA] Got {len(all_prices)} price records, {len(highlights)} highlights")

        result = UsdaPriceData(
            commodities=all_prices,
            highlights=highlights,
        )

        # Cache for next time
        try:
            await save_food_prices_cache("usda", industry, state, result.model_dump(mode="json"))
        except Exception:
            pass

        return result

    except Exception as e:
        logger.error(f"[USDA] NASS query failed: {e}")
        return empty
