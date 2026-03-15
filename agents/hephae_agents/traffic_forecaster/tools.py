"""
Traffic forecaster tools — NWS weather forecast with Firestore cache.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from typing import Any, Optional

import httpx
from google.adk.tools import FunctionTool

logger = logging.getLogger(__name__)

WEATHER_CACHE_TTL_MS = 6 * 60 * 60 * 1000  # 6 hours


async def get_weather_forecast(
    latitude: float,
    longitude: float,
    business_name: Optional[str] = None,
) -> dict[str, Any]:
    """
    Get a 3-day structured weather forecast from the National Weather Service (NWS) API
    using latitude/longitude coordinates. Use this for US locations whenever coordinates are available.

    Args:
        latitude: Latitude of the location.
        longitude: Longitude of the location.
        business_name: The exact business name from the prompt — used as a Firestore cache key.

    Returns:
        dict with forecast data or error.
    """
    cache_key = None
    if business_name:
        cache_key = re.sub(r"/", "_", business_name)
        cache_key = re.sub(r"\s+", "_", cache_key).lower()

    # Check Firestore cache first
    if cache_key:
        try:
            from hephae_common.firebase import get_db; db = get_db()

            doc = db.collection("cache_weather").document(cache_key).get()
            if doc.exists:
                cached = doc.to_dict()
                cached_at = cached.get("cachedAt")
                age = time.time() * 1000 - (cached_at.timestamp() * 1000 if hasattr(cached_at, "timestamp") else 0)
                if age < WEATHER_CACHE_TTL_MS:
                    logger.info(f'[WeatherTool] Cache HIT for "{business_name}" (age: {int(age / 60000)}min)')
                    return {**cached.get("forecast", {}), "source": "NWS (cached)"}
        except Exception as e:
            logger.warning(f"[WeatherTool] Firestore cache read failed: {e}")

    try:
        # Step 1: Get grid endpoint from NWS points API
        async with httpx.AsyncClient(timeout=15.0) as client:
            points_res = await client.get(
                f"https://api.weather.gov/points/{latitude:.4f},{longitude:.4f}",
                headers={"User-Agent": "HephaeHub/1.0 (hephae.co)"},
            )
        if points_res.status_code != 200:
            return {"error": f"NWS points lookup failed: {points_res.status_code}"}

        points_data = points_res.json()
        forecast_url = points_data.get("properties", {}).get("forecast")
        if not forecast_url:
            return {"error": "NWS did not return a forecast URL for these coordinates."}

        # Step 2: Fetch the actual forecast
        async with httpx.AsyncClient(timeout=15.0) as client:
            forecast_res = await client.get(
                forecast_url,
                headers={"User-Agent": "HephaeHub/1.0 (hephae.co)"},
            )
        if forecast_res.status_code != 200:
            return {"error": f"NWS forecast fetch failed: {forecast_res.status_code}"}

        forecast_data = forecast_res.json()
        periods = forecast_data.get("properties", {}).get("periods", [])

        # Group into days
        days: dict[str, Any] = {}
        for period in periods[:6]:
            date = (period.get("startTime") or "").split("T")[0]
            if not date:
                continue
            if date not in days:
                days[date] = {"date": date, "dayOfWeek": period.get("name"), "daytime": None, "nighttime": None}

            entry = {
                "shortForecast": period.get("shortForecast"),
                "temperature": period.get("temperature"),
                "temperatureUnit": period.get("temperatureUnit"),
                "precipitationChance": (period.get("probabilityOfPrecipitation") or {}).get("value"),
                "windSpeed": period.get("windSpeed"),
                "windDirection": period.get("windDirection"),
            }
            if period.get("isDaytime"):
                days[date]["daytime"] = entry
            else:
                days[date]["nighttime"] = entry

        forecast = []
        for day in list(days.values())[:3]:
            daytime = day.get("daytime") or {}
            nighttime = day.get("nighttime") or {}
            forecast.append({
                "date": day["date"],
                "dayOfWeek": day.get("dayOfWeek"),
                "high": daytime.get("temperature"),
                "low": nighttime.get("temperature"),
                "temperatureUnit": daytime.get("temperatureUnit", "F"),
                "shortForecast": daytime.get("shortForecast") or nighttime.get("shortForecast", "Unknown"),
                "precipitationChance": daytime.get("precipitationChance") or nighttime.get("precipitationChance"),
                "windSpeed": daytime.get("windSpeed"),
                "windDirection": daytime.get("windDirection"),
            })

        result = {"source": "NWS (National Weather Service)", "forecast": forecast}

        # Write to Firestore cache
        if cache_key:
            try:
                from hephae_common.firebase import get_db; db = get_db()

                db.collection("cache_weather").document(cache_key).set({
                    "businessName": business_name or cache_key,
                    "forecast": result,
                    "cachedAt": datetime.utcnow(),
                })
                logger.info(f'[WeatherTool] Cache WRITE for "{business_name}"')
            except Exception as e:
                logger.warning(f"[WeatherTool] Firestore cache write failed: {e}")

        return result
    except Exception as e:
        return {"error": f"NWS fetch failed: {e}"}


weather_tool = FunctionTool(func=get_weather_forecast)
