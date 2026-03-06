"""BLS Consumer Price Index API client for food price data."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from backend.config import settings
from backend.lib.db.food_prices import get_cached_food_prices, save_food_prices_cache
from backend.types import BlsCpiData, BlsCpiDataPoint, BlsCpiSeries

logger = logging.getLogger(__name__)

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

# National CPI-U series (not seasonally adjusted — best for YoY comparisons)
# Format: CU U R 0000 <item_code>
#   CU = CPI, U = Urban consumers, U/S = unadjusted/adjusted, R = monthly
#   0000 = US city average
FOOD_CPI_SERIES: dict[str, str] = {
    # Primary food categories
    "Food (all items)": "CUUR0000SAF1",
    "Food at home": "CUUR0000SAF11",
    "Food away from home": "CUUR0000SAFH",

    # Food-at-home subcategories
    "Cereals & bakery": "CUUR0000SAF111",
    "Meats, poultry, fish & eggs": "CUUR0000SAF112",
    "Dairy": "CUUR0000SAF113",
    "Fruits & vegetables": "CUUR0000SAF114",
    "Nonalcoholic beverages": "CUUR0000SAF115",
    "Other food at home": "CUUR0000SAF116",
}

# Detailed series for specific industries
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

# Map business types to which detailed series are relevant
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

# Reverse lookup: series ID → label
_SERIES_ID_TO_LABEL: dict[str, str] = {}
for label, sid in FOOD_CPI_SERIES.items():
    _SERIES_ID_TO_LABEL[sid] = label
for category_series in DETAILED_SERIES.values():
    for label, sid in category_series.items():
        _SERIES_ID_TO_LABEL[sid] = label


def _get_relevant_series(industry: str) -> dict[str, str]:
    """Get the primary food series + industry-relevant detailed series."""
    series = dict(FOOD_CPI_SERIES)  # always include primary

    normalized = industry.lower().strip()
    detailed_cats = INDUSTRY_TO_DETAILED.get(normalized, [])
    if not detailed_cats:
        # Try without trailing 's'
        detailed_cats = INDUSTRY_TO_DETAILED.get(normalized.rstrip("s"), [])

    for cat in detailed_cats:
        if cat in DETAILED_SERIES:
            series.update(DETAILED_SERIES[cat])

    return series


def _parse_series_data(series_data: dict[str, Any]) -> BlsCpiSeries:
    """Parse a single BLS series response into our model."""
    series_id = series_data.get("seriesID", "")
    label = _SERIES_ID_TO_LABEL.get(series_id, series_id)

    data_points: list[BlsCpiDataPoint] = []
    for dp in series_data.get("data", []):
        period = dp.get("period", "")
        if period == "M13":  # skip annual averages
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

        data_points.append(BlsCpiDataPoint(
            year=int(dp.get("year", 0)),
            month=month,
            period=f"{dp['year']}-{month:02d}",
            indexValue=float(dp.get("value", 0)),
            yoyPctChange=yoy,
        ))

    # BLS returns most recent first; sort chronologically
    data_points.sort(key=lambda p: (p.year, p.month))

    return BlsCpiSeries(seriesId=series_id, label=label, data=data_points)


def _generate_highlights(series_list: list[BlsCpiSeries]) -> list[str]:
    """Generate human-readable highlights from the CPI data."""
    highlights: list[str] = []

    for s in series_list:
        if not s.data:
            continue

        latest = s.data[-1]
        if latest.yoyPctChange is not None:
            direction = "up" if latest.yoyPctChange > 0 else "down"
            highlights.append(
                f"{s.label}: {abs(latest.yoyPctChange):.1f}% {direction} year-over-year "
                f"(index {latest.indexValue:.1f}, {latest.period})"
            )

    # Sort by absolute YoY change descending — biggest movers first
    def _sort_key(h: str) -> float:
        try:
            pct = float(h.split(":")[1].split("%")[0].strip())
            return -abs(pct)
        except (IndexError, ValueError):
            return 0
    highlights.sort(key=_sort_key)

    return highlights[:10]


async def query_bls_cpi(industry: str = "") -> BlsCpiData:
    """Query BLS CPI API for food price indexes relevant to an industry.

    Args:
        industry: Optional business type to get industry-specific detailed series.
                  If empty, returns only the primary food categories.

    Returns:
        BlsCpiData with series data and highlights.
    """
    empty = BlsCpiData()

    api_key = settings.BLS_API_KEY
    if not api_key:
        logger.warning("[BLS] No BLS_API_KEY configured — skipping CPI query")
        return empty

    # Cache-first: check Firestore for recent data
    try:
        cached = await get_cached_food_prices("bls", industry or "general")
        if cached:
            return BlsCpiData.model_validate(cached)
    except Exception:
        pass

    try:
        series_map = _get_relevant_series(industry) if industry else FOOD_CPI_SERIES
        series_ids = list(series_map.values())

        # BLS v2 allows max 50 series per request, 20-year span
        now = datetime.utcnow()
        start_year = now.year - 2  # 3 years of data
        end_year = now.year

        payload = {
            "seriesid": series_ids[:50],
            "startyear": str(start_year),
            "endyear": str(end_year),
            "catalog": False,
            "calculations": True,
            "annualaverage": False,
            "aspects": False,
            "registrationkey": api_key,
        }

        logger.info(f"[BLS] Querying {len(series_ids)} CPI series for industry={industry or 'general'}")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(BLS_API_URL, json=payload)

        if response.status_code != 200:
            logger.warning(f"[BLS] API returned {response.status_code}")
            return empty

        data = response.json()
        if data.get("status") != "REQUEST_SUCCEEDED":
            messages = data.get("message", [])
            logger.warning(f"[BLS] API error: {messages}")
            return empty

        results = data.get("Results", {}).get("series", [])
        parsed_series = [_parse_series_data(s) for s in results]

        # Filter out empty series
        parsed_series = [s for s in parsed_series if s.data]

        latest_month = ""
        if parsed_series and parsed_series[0].data:
            latest = parsed_series[0].data[-1]
            latest_month = latest.period

        highlights = _generate_highlights(parsed_series)

        logger.info(f"[BLS] Got {len(parsed_series)} series, latest={latest_month}")

        result = BlsCpiData(
            series=parsed_series,
            latestMonth=latest_month,
            highlights=highlights,
        )

        # Cache for next time
        try:
            await save_food_prices_cache("bls", industry or "general", "", result.model_dump(mode="json"))
        except Exception:
            pass

        return result

    except Exception as e:
        logger.error(f"[BLS] CPI query failed: {e}")
        return empty
