"""EIA (Energy Information Administration) client for state-level energy costs."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

EIA_API_URL = "https://api.eia.gov/v2/electricity/retail-sales/data/"


def _classify_trend(yoy_change: float) -> str:
    """Classify price trend based on year-over-year change."""
    if yoy_change > 2.0:
        return "rising"
    if yoy_change < -2.0:
        return "declining"
    return "stable"


async def query_energy_costs(
    state: str,
    api_key: str = "",
    cache_reader=None,
    cache_writer=None,
) -> dict[str, Any]:
    """Query EIA API for state-level commercial electricity prices.

    Args:
        state: Two-letter state abbreviation (e.g., "NJ", "CA").
        api_key: EIA API key. Falls back to EIA_API_KEY env var.
        cache_reader: Optional async fn(source, key, sub_key) -> dict | None
        cache_writer: Optional async fn(source, key, sub_key, data) -> None

    Returns:
        Dict with latestPrice, priorYearPrice, yoyChange, trend, state, period.
    """
    empty: dict[str, Any] = {
        "latestPrice": 0.0,
        "priorYearPrice": 0.0,
        "yoyChange": 0.0,
        "trend": "stable",
        "state": state,
        "period": "",
    }

    api_key = api_key or os.getenv("EIA_API_KEY", "")
    if not api_key:
        logger.warning("[EIA] No EIA_API_KEY configured")
        return empty

    if not state or len(state.strip()) != 2:
        logger.warning("[EIA] Invalid state code provided")
        return empty

    state = state.upper().strip()

    if cache_reader:
        try:
            cached = await cache_reader("eia", state, "")
            if cached:
                return cached
        except Exception:
            pass

    try:
        params: dict[str, Any] = {
            "api_key": api_key,
            "frequency": "monthly",
            "data[0]": "price",
            "facets[stateid][]": state,
            "facets[sectorid][]": "COM",  # Commercial sector
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": "24",  # 24 months to get YoY comparison
        }

        logger.info(f"[EIA] Querying commercial electricity prices for state={state}")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(EIA_API_URL, params=params)

        if response.status_code != 200:
            logger.warning(f"[EIA] API returned {response.status_code}")
            return empty

        data = response.json()
        records = data.get("response", {}).get("data", [])

        if not records:
            logger.warning(f"[EIA] No data returned for state={state}")
            return empty

        # Records are sorted desc by period; first is latest
        latest_record = records[0]
        latest_price = float(latest_record.get("price") or 0)
        latest_period = latest_record.get("period", "")

        # Find same month from prior year for YoY comparison
        prior_year_price = 0.0
        if latest_period and len(latest_period) >= 7:
            target_year = str(int(latest_period[:4]) - 1)
            target_month = latest_period[5:7]
            target_period = f"{target_year}-{target_month}"
            for record in records:
                if record.get("period", "") == target_period:
                    prior_year_price = float(record.get("price") or 0)
                    break

        yoy_change = 0.0
        if prior_year_price > 0 and latest_price > 0:
            yoy_change = round(
                ((latest_price - prior_year_price) / prior_year_price) * 100, 2
            )

        trend = _classify_trend(yoy_change)

        logger.info(
            f"[EIA] state={state}: {latest_price:.2f} cents/kWh "
            f"(YoY {yoy_change:+.1f}%, {trend})"
        )

        result: dict[str, Any] = {
            "latestPrice": round(latest_price, 2),
            "priorYearPrice": round(prior_year_price, 2),
            "yoyChange": yoy_change,
            "trend": trend,
            "state": state,
            "period": latest_period,
        }

        if cache_writer:
            try:
                await cache_writer("eia", state, "", result)
            except Exception:
                pass

        return result

    except Exception as e:
        logger.error(f"[EIA] Query failed for state={state}: {e}")
        return empty
