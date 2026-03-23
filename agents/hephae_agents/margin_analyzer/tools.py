"""
Margin analyzer tools — market data fetchers + surgery + benchmark functions.

Consolidates:
  - market_data.py content (fetch_commodity_prices, fetch_cpi_data, fetch_fred_indicators)
  - benchmarker.py tool function (fetch_competitor_benchmarks)
  - commodity_watchdog.py tool function (check_commodity_inflation)
  - surgeon.py tool function (perform_surgery)
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote

from google.adk.tools import FunctionTool

from hephae_agents.market_data import (
    fetch_commodity_prices,
    fetch_cpi_data,
    fetch_fred_indicators,
)
from hephae_agents.math.calculation_engine import perform_margin_surgery

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Benchmarker tool
# ---------------------------------------------------------------------------

async def fetch_competitor_benchmarks(location: str, items: list[str], tool_context=None) -> dict[str, Any]:
    """
    Provide a location and an array of item names to fetch local competitor pricing
    and macroeconomic data.

    # STUB — returns mock pricing with random variance. Replace with real competitor
    # pricing API (e.g., Yelp, Google Places) before using in production.
    # Downstream agents (SurgeonAgent) treat this as real data. Returns {"stub": true}
    # flag in macroeconomic_context so callers can detect stub mode.

    Args:
        location: The city and state of the restaurant.
        items: Array of menu item names.

    Returns:
        dict with 'competitors' and 'macroeconomic_context' keys.
    """
    import random

    competitors = []
    for item_name in items:
        variance = random.uniform(-1, 3)
        mock_base_price = 12.00
        competitors.append({
            "competitor_name": f"Competitor near {location}",
            "item_match": item_name,
            "price": round(mock_base_price + variance, 2),
            "source_url": f"https://google.com/maps/search/{quote(location)}+restaurant",
            "distance_miles": 1.2,
        })

    macroeconomic_context: dict[str, Any] = {}

    # Try reading pre-fetched market data from session state (BusinessContext)
    state = {}
    if tool_context and hasattr(tool_context, "state"):
        state = tool_context.state or {}

    cached_cpi = state.get("_market_cpi")
    cached_fred = state.get("_market_fred")

    try:
        if cached_cpi and cached_fred:
            logger.info("[Benchmarker] Using pre-fetched market data from BusinessContext")
            macroeconomic_context = {
                "inflation_cpi": cached_cpi,
                "unemployment_trend": cached_fred,
                "analysis_hint": "Determine if local consumers can absorb a menu price increase.",
            }
        else:
            loc_lc = location.lower()
            region = "Northeast"
            if re.search(r"fl|tx|miami|austin|south|carolina|georgia|alabama", loc_lc):
                region = "South"
            elif re.search(r"il|chicago|midwest|ohio|michigan", loc_lc):
                region = "Midwest"
            elif re.search(r"ca|yountville|west|california|oregon|washington|nv", loc_lc):
                region = "West"

            bls_data = await fetch_cpi_data(region)
            fred_data = await fetch_fred_indicators("UNRATE")

            macroeconomic_context = {
                "inflation_cpi": bls_data,
                "unemployment_trend": fred_data,
                "analysis_hint": "Determine if local consumers can absorb a menu price increase.",
            }
    except Exception as e:
        logger.error(f"[Benchmarker] Market data fetch error: {e}")

    macroeconomic_context["stub"] = True
    return {"competitors": competitors, "macroeconomic_context": macroeconomic_context}


# ---------------------------------------------------------------------------
# Commodity watchdog tool
# ---------------------------------------------------------------------------

async def check_commodity_inflation(terms: list[str], tool_context=None) -> list[dict[str, Any]]:
    """
    Provide an array of menu item names AND category names (pass both) to check
    the latest commodity inflation trends from BLS retail price data.

    Args:
        terms: Mix of menu item names (e.g. "Steak and Eggs") and category names
               (e.g. "Breakfast", "Poultry") — pass all of them together.

    Returns:
        list of CommodityTrend dicts with ingredient, inflation_rate_12mo, trend_description.
    """
    trends: list[dict[str, Any]] = []

    # Map item names AND category names to BLS commodity enum
    commodity_set: set[str] = set()

    for term in terms:
        lc = term.lower()
        if any(kw in lc for kw in ("egg", "breakfast", "omelette", "omelet", "frittata")):
            commodity_set.add("eggs")
        if any(kw in lc for kw in ("cheese", "milk", "dairy", "cream", "butter")):
            commodity_set.add("dairy")
        if any(kw in lc for kw in ("beef", "steak", "burger", "brisket", "ribeye", "sirloin")):
            commodity_set.add("beef")
        if any(kw in lc for kw in ("chicken", "wings", "poultry", "wing", "turkey", "duck")):
            commodity_set.add("poultry")

    # Fallback: always include beef so we prove the data connection works
    if not commodity_set:
        commodity_set.add("beef")

    # Try reading pre-fetched commodity data from session state (BusinessContext)
    state = {}
    if tool_context and hasattr(tool_context, "state"):
        state = tool_context.state or {}
    cached_prices = state.get("_market_commodity_prices") or {}

    for commodity in commodity_set:
        try:
            # Use pre-fetched data if available, otherwise fetch live
            data = cached_prices.get(commodity)
            if data:
                logger.info(f"[Commodity Watchdog] Using pre-fetched data for {commodity}")
            else:
                data = await fetch_commodity_prices(commodity)

            if data and data.get("commodity"):
                trend_str = data.get("trend30Day", "0%")
                inflation_val = float(re.sub(r"[^0-9.\-]", "", trend_str) or "2.4")
                trends.append({
                    "ingredient": data["commodity"].upper(),
                    "inflation_rate_12mo": inflation_val,
                    "trend_description": (
                        f"BLS Retail Price: {data.get('pricePerUnit')}. "
                        f"30-day trend: {data.get('trend30Day')}. "
                        f"Source: {data.get('source')}"
                    ),
                })
        except Exception as e:
            logger.error(f"[Commodity Watchdog] Fetch error for {commodity}: {e}")

    return trends


# ---------------------------------------------------------------------------
# Surgeon tool
# ---------------------------------------------------------------------------

async def perform_surgery(
    items: list[dict[str, Any]],
    competitors: list[dict[str, Any]],
    commodities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Provide items, competitors, and commodities to calculate the absolute optimal price
    and identify revenue leakage for the restaurant's menu.

    Args:
        items: Array of MenuItem dicts.
        competitors: Array of CompetitorPrice dicts.
        commodities: Array of CommodityTrend dicts.

    Returns:
        list of MenuAnalysisItem dicts with calculated leakage.
    """
    return perform_margin_surgery(items, competitors, commodities)


# ---------------------------------------------------------------------------
# Pre-wrapped FunctionTool instances
# ---------------------------------------------------------------------------

benchmark_tool = FunctionTool(func=fetch_competitor_benchmarks)
commodity_inflation_tool = FunctionTool(func=check_commodity_inflation)
surgery_tool = FunctionTool(func=perform_surgery)
