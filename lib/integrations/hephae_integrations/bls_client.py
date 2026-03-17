"""BLS Consumer Price Index API client for food price data."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BLS_V1_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
BLS_V2_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

FOOD_CPI_SERIES: dict[str, str] = {
    "Food (all items)": "CUUR0000SAF1",
    "Food at home": "CUUR0000SAF11",
    "Food away from home": "CUUR0000SAFH",
    "Cereals & bakery": "CUUR0000SAF111",
    "Meats, poultry, fish & eggs": "CUUR0000SAF112",
    "Dairy": "CUUR0000SAF113",
    "Fruits & vegetables": "CUUR0000SAF114",
    "Nonalcoholic beverages": "CUUR0000SAF115",
    "Other food at home": "CUUR0000SAF116",
}

DETAILED_SERIES: dict[str, dict[str, str]] = {
    "meats": {
        "Beef & veal": "CUUR0000SEFC01",
        "Pork": "CUUR0000SEFC02",
        "Poultry": "CUUR0000SEFD",
        "Fish & seafood": "CUUR0000SEFE",
        "Eggs": "CUUR0000SEFG",
    },
    "dairy": {
        "Milk": "CUUR0000SEFJ",
        "Cheese": "CUUR0000SEFK",
        "Ice cream": "CUUR0000SEFL",
    },
    "produce": {
        "Fresh fruits": "CUUR0000SEFN",
        "Fresh vegetables": "CUUR0000SEFP",
        "Processed fruits & vegetables": "CUUR0000SEFR",
    },
    "bakery": {
        "Cereals": "CUUR0000SEFA",
        "Bakery products": "CUUR0000SEFB",
    },
    "beverages": {
        "Carbonated drinks": "CUUR0000SEFQ",
        "Coffee": "CUUR0000SS02011",
    },
}

INDUSTRY_TO_DETAILED: dict[str, list[str]] = {
    "bakeries": ["bakery"],
    "bakery": ["bakery"],
    "pizza": ["bakery", "dairy", "meats"],
    "pizzeria": ["bakery", "dairy", "meats"],
    "restaurants": ["meats", "produce", "dairy"],
    "restaurant": ["meats", "produce", "dairy"],
    "coffee": ["beverages"],
    "coffee shops": ["beverages"],
    "cafe": ["beverages", "bakery"],
    "ice cream": ["dairy"],
    "gelato": ["dairy"],
    "tacos": ["meats", "produce"],
    "taqueria": ["meats", "produce"],
    "seafood": ["meats"],
    "fish market": ["meats"],
    "butcher": ["meats"],
    "grocery": ["meats", "produce", "dairy", "bakery", "beverages"],
    "supermarket": ["meats", "produce", "dairy", "bakery", "beverages"],
    "juice bar": ["produce", "beverages"],
    "smoothie": ["produce", "dairy", "beverages"],
    "deli": ["meats", "dairy", "bakery"],
}

_SERIES_ID_TO_LABEL: dict[str, str] = {}
for _label, _sid in FOOD_CPI_SERIES.items():
    _SERIES_ID_TO_LABEL[_sid] = _label
for _category_series in DETAILED_SERIES.values():
    for _label, _sid in _category_series.items():
        _SERIES_ID_TO_LABEL[_sid] = _label


def _get_relevant_series(industry: str) -> dict[str, str]:
    series = dict(FOOD_CPI_SERIES)
    normalized = industry.lower().strip()
    detailed_cats = INDUSTRY_TO_DETAILED.get(normalized, [])
    if not detailed_cats:
        detailed_cats = INDUSTRY_TO_DETAILED.get(normalized.rstrip("s"), [])
    for cat in detailed_cats:
        if cat in DETAILED_SERIES:
            series.update(DETAILED_SERIES[cat])
    return series


def _parse_series_data(series_data: dict[str, Any]) -> dict[str, Any]:
    series_id = series_data.get("seriesID", "")
    label = _SERIES_ID_TO_LABEL.get(series_id, series_id)

    data_points: list[dict[str, Any]] = []
    for dp in series_data.get("data", []):
        period = dp.get("period", "")
        if period == "M13":
            continue

        yoy: float | None = None
        calcs = dp.get("calculations", {})
        pct_changes = calcs.get("pct_changes", {})
        if "12" in pct_changes:
            try:
                yoy = float(pct_changes["12"])
            except (ValueError, TypeError):
                pass

        try:
            month = int(period.replace("M", ""))
        except ValueError:
            continue

        try:
            index_val = float(dp.get("value", 0))
        except (ValueError, TypeError):
            continue

        data_points.append({
            "year": int(dp.get("year", 0)),
            "month": month,
            "period": f"{dp['year']}-{month:02d}",
            "indexValue": index_val,
            "yoyPctChange": yoy,
        })

    data_points.sort(key=lambda p: (p["year"], p["month"]))
    return {"seriesId": series_id, "label": label, "data": data_points}


def _generate_highlights(series_list: list[dict[str, Any]]) -> list[str]:
    highlights: list[str] = []
    for s in series_list:
        if not s.get("data"):
            continue
        latest = s["data"][-1]
        if latest.get("yoyPctChange") is not None:
            direction = "up" if latest["yoyPctChange"] > 0 else "down"
            highlights.append(
                f"{s['label']}: {abs(latest['yoyPctChange']):.1f}% {direction} year-over-year "
                f"(index {latest['indexValue']:.1f}, {latest['period']})"
            )

    def _sort_key(h: str) -> float:
        try:
            pct = float(h.split(":")[1].split("%")[0].strip())
            return -abs(pct)
        except (IndexError, ValueError):
            return 0
    highlights.sort(key=_sort_key)
    return highlights[:10]


def compute_price_deltas(series_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compute month-over-month and year-over-year deltas for each CPI series.

    Returns a list of delta dicts suitable for pulse agent consumption:
    [{"label": str, "latestPeriod": str, "yoyPctChange": float|None,
      "momPctChange": float|None, "direction": str, "indexValue": float}]
    """
    deltas: list[dict[str, Any]] = []
    for s in series_list:
        data = s.get("data", [])
        if len(data) < 2:
            continue

        latest = data[-1]
        prev = data[-2]

        yoy = latest.get("yoyPctChange")

        # Month-over-month from index values
        mom: float | None = None
        if prev["indexValue"] > 0 and latest["indexValue"] > 0:
            mom = round(
                ((latest["indexValue"] - prev["indexValue"]) / prev["indexValue"]) * 100,
                2,
            )

        direction = "stable"
        ref = yoy if yoy is not None else mom
        if ref is not None:
            if ref > 1.0:
                direction = "rising"
            elif ref < -1.0:
                direction = "declining"

        deltas.append({
            "label": s["label"],
            "latestPeriod": latest["period"],
            "indexValue": latest["indexValue"],
            "yoyPctChange": yoy,
            "momPctChange": mom,
            "direction": direction,
        })

    # Sort by absolute YoY change descending (most impactful first)
    deltas.sort(key=lambda d: abs(d.get("yoyPctChange") or 0), reverse=True)
    return deltas


async def query_bls_cpi(
    industry: str = "",
    api_key: str = "",
    cache_reader=None,
    cache_writer=None,
) -> dict[str, Any]:
    """Query BLS CPI API for food price indexes relevant to an industry.

    Args:
        industry: Business type for industry-specific series.
        api_key: BLS API key. Falls back to BLS_API_KEY env var.
        cache_reader: Optional async fn(source, industry, state) -> dict | None
        cache_writer: Optional async fn(source, industry, state, data) -> None

    Returns:
        Dict with series, latestMonth, and highlights.
    """
    empty: dict[str, Any] = {"series": [], "latestMonth": "", "highlights": []}

    api_key = api_key or os.getenv("BLS_API_KEY", "")

    if cache_reader:
        try:
            cached = await cache_reader("bls", industry or "general", "")
            if cached:
                return cached
        except Exception:
            pass

    try:
        series_map = _get_relevant_series(industry) if industry else FOOD_CPI_SERIES
        series_ids = list(series_map.values())

        now = datetime.utcnow()
        start_year = now.year - 2
        end_year = now.year

        # Use v2 (with key, richer data) if available, otherwise v1 (no key, basic data)
        if api_key:
            api_url = BLS_V2_URL
            payload: dict[str, Any] = {
                "seriesid": series_ids[:50],
                "startyear": str(start_year),
                "endyear": str(end_year),
                "catalog": False,
                "calculations": True,
                "annualaverage": False,
                "aspects": False,
                "registrationkey": api_key,
            }
            logger.info(f"[BLS] Querying v2 API ({len(series_ids)} series, industry={industry or 'general'})")
        else:
            # v1: no key needed, max 25 series, no calculations field
            api_url = BLS_V1_URL
            payload = {
                "seriesid": series_ids[:25],
                "startyear": str(start_year),
                "endyear": str(end_year),
            }
            logger.info(f"[BLS] Querying v1 API (no key, {min(len(series_ids), 25)} series)")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(api_url, json=payload)

        if response.status_code != 200:
            logger.warning(f"[BLS] API returned {response.status_code}")
            return empty

        data = response.json()
        if data.get("status") != "REQUEST_SUCCEEDED":
            msgs = data.get("message", [])
            logger.warning(f"[BLS] API error: {msgs}")
            # If v2 failed due to invalid key, retry with v1
            if api_key and api_url == BLS_V2_URL and any("invalid" in str(m).lower() or "key" in str(m).lower() for m in msgs):
                logger.info("[BLS] v2 key invalid — falling back to v1 (no key)")
                v1_payload = {
                    "seriesid": series_ids[:25],
                    "startyear": str(start_year),
                    "endyear": str(end_year),
                }
                async with httpx.AsyncClient(timeout=30) as v1_client:
                    response = await v1_client.post(BLS_V1_URL, json=v1_payload)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") != "REQUEST_SUCCEEDED":
                        return empty
                else:
                    return empty
            else:
                return empty

        results = data.get("Results", {}).get("series", [])
        parsed_series = [_parse_series_data(s) for s in results]
        parsed_series = [s for s in parsed_series if s.get("data")]

        latest_month = ""
        if parsed_series and parsed_series[0].get("data"):
            latest_month = parsed_series[0]["data"][-1]["period"]

        highlights = _generate_highlights(parsed_series)

        logger.info(f"[BLS] Got {len(parsed_series)} series, latest={latest_month}")

        result = {"series": parsed_series, "latestMonth": latest_month, "highlights": highlights}

        if cache_writer:
            try:
                await cache_writer("bls", industry or "general", "", result)
            except Exception:
                pass

        return result

    except Exception as e:
        logger.error(f"[BLS] CPI query failed: {e}")
        return empty
