"""FBI Uniform Crime Reporting (UCR) client via Crime Data Explorer API."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

FBI_CDE_BASE_URL = "https://api.usa.gov/crime/fbi/sapi/api"

# Pre-computed national averages (2023 FBI UCR data) used as fallback
# when API key is unavailable or the API is unreachable.
_NATIONAL_AVERAGES: dict[str, Any] = {
    "violentCrimeRate": 380.7,  # per 100k population
    "propertyCrimeRate": 1832.3,  # per 100k population
    "trend": "stable",
    "safetyLevel": "moderate",
    "state": "US",
    "county": "",
    "period": "2023",
    "source": "national_average",
}


def _classify_safety(violent_rate: float) -> str:
    """Classify safety level based on violent crime rate per 100k."""
    if violent_rate < 200:
        return "high"
    if violent_rate < 450:
        return "moderate"
    return "low"


def _classify_trend(current_rate: float, prior_rate: float) -> str:
    """Classify trend comparing current vs prior year rates."""
    if prior_rate <= 0:
        return "stable"
    pct_change = ((current_rate - prior_rate) / prior_rate) * 100
    if pct_change < -3.0:
        return "improving"
    if pct_change > 3.0:
        return "worsening"
    return "stable"


async def query_crime_stats(
    state: str,
    county: str = "",
    api_key: str = "",
    cache_reader=None,
    cache_writer=None,
) -> dict[str, Any]:
    """Query FBI Crime Data Explorer for crime statistics.

    Args:
        state: Two-letter state abbreviation (e.g., "NJ", "CA").
        county: Optional county name for context (included in output).
        api_key: FBI API key. Falls back to FBI_API_KEY env var.
        cache_reader: Optional async fn(source, key, sub_key) -> dict | None
        cache_writer: Optional async fn(source, key, sub_key, data) -> None

    Returns:
        Dict with violentCrimeRate, propertyCrimeRate, trend, safetyLevel,
        state, county, period.
    """
    empty: dict[str, Any] = {
        "violentCrimeRate": 0.0,
        "propertyCrimeRate": 0.0,
        "trend": "stable",
        "safetyLevel": "moderate",
        "state": state,
        "county": county,
        "period": "",
    }

    if not state or len(state.strip()) != 2:
        logger.warning("[FBI_UCR] Invalid state code provided")
        return empty

    state = state.upper().strip()

    if cache_reader:
        try:
            cached = await cache_reader("fbi_ucr", state, county)
            if cached:
                return cached
        except Exception:
            pass

    api_key = api_key or os.getenv("FBI_API_KEY", "")
    if not api_key:
        logger.warning("[FBI_UCR] No FBI_API_KEY configured, using national averages")
        fallback = dict(_NATIONAL_AVERAGES)
        fallback["state"] = state
        fallback["county"] = county
        return fallback

    try:
        # Query violent crime summarized data for the state
        violent_url = (
            f"{FBI_CDE_BASE_URL}/summarized/state/{state}/violent-crime"
            f"?from=2021&to=2025&API_KEY={api_key}"
        )
        property_url = (
            f"{FBI_CDE_BASE_URL}/summarized/state/{state}/property-crime"
            f"?from=2021&to=2025&API_KEY={api_key}"
        )

        logger.info(f"[FBI_UCR] Querying crime stats for state={state}")

        async with httpx.AsyncClient(timeout=30) as client:
            violent_resp = await client.get(violent_url)
            property_resp = await client.get(property_url)

        # Parse violent crime data
        violent_rate = 0.0
        prior_violent_rate = 0.0
        latest_year = ""

        if violent_resp.status_code == 200:
            violent_data = violent_resp.json()
            results = violent_data.get("results", [])
            if results:
                # Sort by year descending to get most recent
                results.sort(key=lambda r: int(r.get("data_year", 0)), reverse=True)
                latest = results[0]
                population = int(latest.get("population", 1))
                actual = int(latest.get("actual", 0))
                latest_year = str(latest.get("data_year", ""))
                if population > 0:
                    violent_rate = round((actual / population) * 100_000, 1)

                # Get prior year for trend
                if len(results) > 1:
                    prior = results[1]
                    prior_pop = int(prior.get("population", 1))
                    prior_actual = int(prior.get("actual", 0))
                    if prior_pop > 0:
                        prior_violent_rate = round((prior_actual / prior_pop) * 100_000, 1)
        else:
            logger.warning(f"[FBI_UCR] Violent crime API returned {violent_resp.status_code}")

        # Parse property crime data
        property_rate = 0.0

        if property_resp.status_code == 200:
            property_data = property_resp.json()
            results = property_data.get("results", [])
            if results:
                results.sort(key=lambda r: int(r.get("data_year", 0)), reverse=True)
                latest = results[0]
                population = int(latest.get("population", 1))
                actual = int(latest.get("actual", 0))
                if population > 0:
                    property_rate = round((actual / population) * 100_000, 1)
                if not latest_year:
                    latest_year = str(latest.get("data_year", ""))
        else:
            logger.warning(f"[FBI_UCR] Property crime API returned {property_resp.status_code}")

        # If we got no data at all, fall back to national averages
        if violent_rate == 0.0 and property_rate == 0.0:
            logger.warning(f"[FBI_UCR] No data for state={state}, using national averages")
            fallback = dict(_NATIONAL_AVERAGES)
            fallback["state"] = state
            fallback["county"] = county
            return fallback

        trend = _classify_trend(violent_rate, prior_violent_rate)
        safety = _classify_safety(violent_rate)

        logger.info(
            f"[FBI_UCR] state={state}: violent={violent_rate}/100k, "
            f"property={property_rate}/100k, safety={safety}, trend={trend}"
        )

        result: dict[str, Any] = {
            "violentCrimeRate": violent_rate,
            "propertyCrimeRate": property_rate,
            "trend": trend,
            "safetyLevel": safety,
            "state": state,
            "county": county,
            "period": latest_year,
        }

        if cache_writer:
            try:
                await cache_writer("fbi_ucr", state, county, result)
            except Exception:
                pass

        return result

    except Exception as e:
        logger.error(f"[FBI_UCR] Query failed for state={state}: {e}")
        # Fall back to national averages on any failure
        fallback = dict(_NATIONAL_AVERAGES)
        fallback["state"] = state
        fallback["county"] = county
        return fallback
