"""
LocatorAgent — resolves business identity from a search query.

Uses Gemini with Google Search grounding to extract name, address, URL, coordinates.
Falls back to Nominatim for geocoding if LLM coordinates are invalid.
Port of src/agents/discovery/locator.ts.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

from google import genai
from google.genai import types
import httpx

from hephae_common.model_config import AgentModels
from hephae_common.model_fallback import generate_with_fallback

logger = logging.getLogger(__name__)


async def _geocode_address(address: str) -> Optional[dict[str, float]]:
    """Geocode an address via Google Geocoding API (primary) or Nominatim (fallback)."""
    # Primary: Google Geocoding API
    api_key = os.environ.get("NEXT_PUBLIC_GOOGLE_MAPS_API_KEY") or os.environ.get("GOOGLE_MAPS_API_KEY")
    if api_key:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(
                    "https://maps.googleapis.com/maps/api/geocode/json",
                    params={"address": address, "key": api_key},
                )
            if res.status_code == 200:
                data = res.json()
                if data.get("status") == "OK" and data.get("results"):
                    loc = data["results"][0]["geometry"]["location"]
                    lat, lng = loc["lat"], loc["lng"]
                    if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
                        logger.info(f'[LocatorAgent] Google geocoded "{address}" -> [{lat}, {lng}]')
                        return {"lat": lat, "lng": lng}
        except Exception as e:
            logger.warning(f"[LocatorAgent] Google Geocoding failed: {e}")

    # Fallback: OpenStreetMap Nominatim
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": address, "format": "json", "limit": "1"},
                headers={"User-Agent": "Hephae/1.0 (business-intelligence)"},
            )
        if res.status_code == 200:
            results = res.json()
            if results:
                lat = float(results[0]["lat"])
                lng = float(results[0]["lon"])
                if lat != 0 or lng != 0:
                    logger.info(f'[LocatorAgent] Nominatim geocoded "{address}" -> [{lat}, {lng}]')
                    return {"lat": lat, "lng": lng}
    except Exception as e:
        logger.warning(f"[LocatorAgent] Nominatim geocoding failed: {e}")

    return None


class LocatorAgent:
    @staticmethod
    async def resolve(query: str) -> dict[str, Any]:
        """Resolve a business query to a BaseIdentity dict."""
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Missing GEMINI_API_KEY")

        logger.info(f'[LocatorAgent] Resolving identity for: "{query}"...')

        client = genai.Client(api_key=api_key)

        prompt = f"""Use Google Search to find the official identity details for the business matching the query: "{query}".
Return ONLY a valid JSON object with the following keys:
- "name": Official name of the business
- "address": Full physical address, or City/State if exact address is unknown
- "officialUrl": The official website URL (or Facebook/Yelp if none exists)
- "lat": numerical latitude
- "lng": numerical longitude
Do not include any markdown, explanations, or quotes outside the JSON."""

        result = await generate_with_fallback(
            client,
            model=AgentModels.PRIMARY_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )
        response_text = result.text

        try:
            clean_json = re.sub(r"```json\n?|\n?```", "", response_text).strip()
            data = json.loads(clean_json)
        except (json.JSONDecodeError, ValueError):
            logger.error(f"[LocatorAgent] Failed to parse JSON. Raw response: {response_text}")
            raise ValueError("LocatorAgent failed to extract structured data from Gemini.")

        resolved_url = data.get("officialUrl", "")
        if resolved_url and not resolved_url.startswith("http"):
            resolved_url = "https://" + resolved_url

        # Validate coordinates from LLM
        llm_lat = data.get("lat")
        llm_lng = data.get("lng")
        has_valid_coords = (
            isinstance(llm_lat, (int, float))
            and isinstance(llm_lng, (int, float))
            and not (llm_lat == 0 and llm_lng == 0)
        )

        coordinates = None
        if has_valid_coords:
            coordinates = {"lat": llm_lat, "lng": llm_lng}
        else:
            logger.warning(
                f"[LocatorAgent] LLM returned invalid coordinates [{llm_lat}, {llm_lng}], "
                "falling back to geocoding..."
            )
            geocoded = await _geocode_address(data.get("address") or f"{data.get('name')} {query}")
            if geocoded:
                coordinates = geocoded
            else:
                logger.error("[LocatorAgent] All geocoding failed — coordinates will be None")

        logger.info(
            f"[LocatorAgent] Found: {data.get('name')} at {resolved_url} "
            f"({data.get('address')}) [{coordinates}]"
        )

        return {
            "name": data.get("name", ""),
            "address": data.get("address"),
            "officialUrl": resolved_url,
            "coordinates": coordinates,
        }
