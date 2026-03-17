"""National Weather Service API client for 7-day weather forecasts by zip code."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_ZIPPOPOTAM_URL = "https://api.zippopotam.us/us"
_NWS_POINTS_URL = "https://api.weather.gov/points"
_NWS_ALERTS_URL = "https://api.weather.gov/alerts/active"
_USER_AGENT = "Hephae/1.0 (contact@hephae.co)"

_WEEKEND_NAMES = {"Saturday", "Sunday", "Saturday Night", "Sunday Night"}


def _classify_outdoor_favorability(periods: list[dict[str, Any]]) -> str:
    """Rate outdoor favorability based on weekend weather periods."""
    weekend_periods = [
        p for p in periods
        if p.get("name") in _WEEKEND_NAMES
    ]
    if not weekend_periods:
        return "moderate"

    bad_count = 0
    for p in weekend_periods:
        forecast_lower = p.get("shortForecast", "").lower()
        temp = p.get("temperature", 70)
        if any(w in forecast_lower for w in ("rain", "storm", "snow", "sleet", "thunder")):
            bad_count += 1
        elif temp < 32 or temp > 100:
            bad_count += 1

    ratio = bad_count / len(weekend_periods)
    if ratio <= 0.25:
        return "high"
    elif ratio <= 0.5:
        return "moderate"
    return "low"


def _build_summary(periods: list[dict[str, Any]]) -> str:
    """Build a one-line weather summary from forecast periods."""
    if not periods:
        return ""

    parts: list[str] = []
    for p in periods[:4]:
        name = p.get("name", "")
        temp = p.get("temperature", "?")
        short = p.get("shortForecast", "")
        parts.append(f"{temp}F {name}")

    rain_days = [
        p.get("name", "")
        for p in periods
        if any(w in p.get("shortForecast", "").lower() for w in ("rain", "storm", "shower"))
    ]

    summary = ", ".join(parts[:3])
    if rain_days:
        summary += f"; rain {rain_days[0]}"
    return summary


def _parse_precip_chance(detailed: str) -> int:
    """Extract precipitation chance percentage from detailed forecast text."""
    match = re.search(r"(\d+)\s*percent", detailed.lower())
    if match:
        return int(match.group(1))
    return 0


async def _geocode_zip(zip_code: str, client: httpx.AsyncClient) -> tuple[float, float] | None:
    """Convert zip code to lat/lon using Zippopotam.us API."""
    try:
        resp = await client.get(f"{_ZIPPOPOTAM_URL}/{zip_code}")
        if resp.status_code != 200:
            logger.warning(f"[NWS] Zippopotam returned {resp.status_code} for zip {zip_code}")
            return None
        data = resp.json()
        places = data.get("places", [])
        if not places:
            return None
        lat = float(places[0]["latitude"])
        lon = float(places[0]["longitude"])
        return lat, lon
    except Exception as e:
        logger.error(f"[NWS] Zip geocode failed for {zip_code}: {e}")
        return None


async def _get_forecast_url(lat: float, lon: float, client: httpx.AsyncClient) -> str | None:
    """Call NWS points API to get the forecast URL for a lat/lon."""
    try:
        resp = await client.get(
            f"{_NWS_POINTS_URL}/{lat:.4f},{lon:.4f}",
            headers={"User-Agent": _USER_AGENT, "Accept": "application/geo+json"},
        )
        if resp.status_code != 200:
            logger.warning(f"[NWS] Points API returned {resp.status_code} for ({lat}, {lon})")
            return None
        data = resp.json()
        return data.get("properties", {}).get("forecast")
    except Exception as e:
        logger.error(f"[NWS] Points API failed: {e}")
        return None


async def _fetch_forecast(forecast_url: str, client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """Fetch the 7-day forecast from a NWS forecast URL."""
    try:
        resp = await client.get(
            forecast_url,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/geo+json"},
        )
        if resp.status_code != 200:
            logger.warning(f"[NWS] Forecast API returned {resp.status_code}")
            return []
        data = resp.json()
        raw_periods = data.get("properties", {}).get("periods", [])

        periods: list[dict[str, Any]] = []
        for p in raw_periods[:14]:
            periods.append({
                "name": p.get("name", ""),
                "temperature": p.get("temperature", 0),
                "temperatureUnit": p.get("temperatureUnit", "F"),
                "shortForecast": p.get("shortForecast", ""),
                "detailedForecast": p.get("detailedForecast", ""),
                "windSpeed": p.get("windSpeed", ""),
                "precipChance": _parse_precip_chance(p.get("detailedForecast", "")),
            })
        return periods
    except Exception as e:
        logger.error(f"[NWS] Forecast fetch failed: {e}")
        return []


async def _fetch_alerts(lat: float, lon: float, client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """Fetch active weather alerts for a lat/lon point."""
    try:
        resp = await client.get(
            _NWS_ALERTS_URL,
            params={"point": f"{lat:.4f},{lon:.4f}"},
            headers={"User-Agent": _USER_AGENT, "Accept": "application/geo+json"},
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        alerts: list[dict[str, Any]] = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            alerts.append({
                "event": props.get("event", ""),
                "headline": props.get("headline", ""),
                "severity": props.get("severity", ""),
                "description": props.get("description", ""),
            })
        return alerts
    except Exception as e:
        logger.error(f"[NWS] Alerts fetch failed: {e}")
        return []


async def query_weather_forecast(
    zip_code: str,
    cache_reader=None,
    cache_writer=None,
) -> dict[str, Any]:
    """Query National Weather Service for 7-day forecast by zip code.

    Args:
        zip_code: US zip code to get forecast for.
        cache_reader: Optional async fn(source, key, sub) -> dict | None
        cache_writer: Optional async fn(source, key, sub, data) -> None

    Returns:
        Dict with forecast, summary, alerts, and outdoorFavorability.
    """
    empty: dict[str, Any] = {
        "forecast": [],
        "summary": "",
        "alerts": [],
        "outdoorFavorability": "moderate",
    }

    if cache_reader:
        try:
            cached = await cache_reader("nws", zip_code, "")
            if cached:
                return cached
        except Exception:
            pass

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Step 1: Geocode zip code
            coords = await _geocode_zip(zip_code, client)
            if not coords:
                logger.warning(f"[NWS] Could not geocode zip {zip_code}")
                return empty

            lat, lon = coords
            logger.info(f"[NWS] Geocoded {zip_code} → ({lat:.4f}, {lon:.4f})")

            # Step 2: Get forecast office URL
            forecast_url = await _get_forecast_url(lat, lon, client)
            if not forecast_url:
                return empty

            # Step 3: Fetch forecast and alerts in parallel
            forecast_periods = await _fetch_forecast(forecast_url, client)
            alerts = await _fetch_alerts(lat, lon, client)

        summary = _build_summary(forecast_periods)
        favorability = _classify_outdoor_favorability(forecast_periods)

        logger.info(
            f"[NWS] Got {len(forecast_periods)} periods, "
            f"{len(alerts)} alerts, favorability={favorability}"
        )

        result: dict[str, Any] = {
            "forecast": forecast_periods,
            "summary": summary,
            "alerts": alerts,
            "outdoorFavorability": favorability,
        }

        if cache_writer:
            try:
                await cache_writer("nws", zip_code, "", result)
            except Exception:
                pass

        return result

    except Exception as e:
        logger.error(f"[NWS] Weather forecast query failed: {e}")
        return empty
