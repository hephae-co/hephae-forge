"""USDA NASS QuickStats API client for agricultural commodity prices."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

NASS_API_URL = "https://quickstats.nass.usda.gov/api/api_GET/"

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
    "coffee": [{"commodity_desc": "MILK", "statisticcat_desc": "PRICE RECEIVED"}],
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
    "seafood": [{"commodity_desc": "CATFISH", "statisticcat_desc": "PRICE RECEIVED"}],
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

DEFAULT_FOOD_COMMODITIES: list[dict[str, str]] = [
    {"commodity_desc": "CATTLE", "statisticcat_desc": "PRICE RECEIVED"},
    {"commodity_desc": "MILK", "statisticcat_desc": "PRICE RECEIVED"},
    {"commodity_desc": "EGGS", "statisticcat_desc": "PRICE RECEIVED"},
    {"commodity_desc": "WHEAT", "statisticcat_desc": "PRICE RECEIVED"},
]


def _get_commodities_for_industry(industry: str) -> list[dict[str, str]]:
    normalized = industry.lower().strip()
    if normalized in INDUSTRY_COMMODITIES:
        return INDUSTRY_COMMODITIES[normalized]
    singular = normalized.rstrip("s")
    if singular in INDUSTRY_COMMODITIES:
        return INDUSTRY_COMMODITIES[singular]
    for key in INDUSTRY_COMMODITIES:
        if key in normalized or normalized in key:
            return INDUSTRY_COMMODITIES[key]
    return DEFAULT_FOOD_COMMODITIES


async def _fetch_commodity(
    client: httpx.AsyncClient, api_key: str,
    commodity: str, stat_cat: str, state: str = "", year_start: int = 0,
) -> list[dict[str, Any]]:
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
        if response.status_code in (400, 404):
            return []
        if response.status_code != 200:
            logger.warning(f"[USDA] API returned {response.status_code} for {commodity}")
            return []
        return response.json().get("data", [])
    except Exception as e:
        logger.error(f"[USDA] Fetch failed for {commodity}: {e}")
        return []


def _parse_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prices: list[dict[str, Any]] = []
    for r in records:
        value_str = r.get("Value", "").strip().replace(",", "")
        if not value_str or value_str in ("(D)", "(NA)", "(Z)", "(S)"):
            continue
        try:
            value = float(value_str)
        except ValueError:
            continue
        prices.append({
            "commodity": r.get("commodity_desc", ""),
            "year": int(r.get("year", 0)),
            "period": r.get("reference_period_desc", r.get("freq_desc", "")),
            "value": value,
            "unit": r.get("unit_desc", ""),
            "state": r.get("state_name", r.get("state_alpha", "US")),
        })
    prices.sort(key=lambda p: (p["commodity"], p["year"]))
    return prices


def _generate_highlights(prices: list[dict[str, Any]]) -> list[str]:
    highlights: list[str] = []
    by_commodity: dict[str, list[dict[str, Any]]] = {}
    for p in prices:
        by_commodity.setdefault(p["commodity"], []).append(p)
    for commodity, records in by_commodity.items():
        records.sort(key=lambda r: r["year"])
        if len(records) < 2:
            if records:
                r = records[-1]
                highlights.append(f"{commodity}: ${r['value']:.2f}/{r['unit']} ({r['year']})")
            continue
        latest = records[-1]
        prev = records[-2]
        if prev["value"] > 0:
            pct_change = ((latest["value"] - prev["value"]) / prev["value"]) * 100
            direction = "up" if pct_change > 0 else "down"
            highlights.append(
                f"{commodity}: ${latest['value']:.2f}/{latest['unit']} ({latest['year']}), "
                f"{abs(pct_change):.1f}% {direction} from {prev['year']}"
            )
        else:
            highlights.append(f"{commodity}: ${latest['value']:.2f}/{latest['unit']} ({latest['year']})")
    return highlights


async def query_usda_prices(
    industry: str,
    state: str = "",
    api_key: str = "",
    cache_reader=None,
    cache_writer=None,
) -> dict[str, Any]:
    """Query USDA NASS for agricultural commodity prices.

    Returns dict with commodities and highlights lists.
    """
    empty: dict[str, Any] = {"commodities": [], "highlights": []}

    api_key = api_key or os.getenv("USDA_NASS_API_KEY", "")
    if not api_key:
        logger.warning("[USDA] No USDA_NASS_API_KEY configured")
        return empty

    if cache_reader:
        try:
            cached = await cache_reader("usda", industry, state)
            if cached:
                return cached
        except Exception:
            pass

    try:
        commodities = _get_commodities_for_industry(industry)
        if not commodities:
            return empty
        year_start = datetime.utcnow().year - 3

        logger.info(f"[USDA] Querying {len(commodities)} commodities for industry={industry}, state={state or 'national'}")

        all_prices: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=30) as client:
            for commodity_params in commodities:
                records = await _fetch_commodity(
                    client=client, api_key=api_key,
                    commodity=commodity_params["commodity_desc"],
                    stat_cat=commodity_params["statisticcat_desc"],
                    state=state, year_start=year_start,
                )
                all_prices.extend(_parse_records(records))

        highlights = _generate_highlights(all_prices)
        logger.info(f"[USDA] Got {len(all_prices)} price records, {len(highlights)} highlights")

        result = {"commodities": all_prices, "highlights": highlights}

        if cache_writer:
            try:
                await cache_writer("usda", industry, state, result)
            except Exception:
                pass

        return result
    except Exception as e:
        logger.error(f"[USDA] NASS query failed: {e}")
        return empty
