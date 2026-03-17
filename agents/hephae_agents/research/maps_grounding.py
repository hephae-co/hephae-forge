"""Google Maps Grounding Lite — competitive landscape via MCP.

Uses Google's Maps Grounding Lite MCP server to get Google-quality place data
for business density analysis. Supplements OSM with ratings, reviews, and
more complete business listings.

The MCP server is at https://mapstools.googleapis.com/mcp and provides
search_places, get_place_details, etc. ADK connects natively via MCPToolset.

Rate limits: 100 searches/min, 1,000/day per project.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

from hephae_api.config import AgentModels
from hephae_common.adk_helpers import run_agent_to_json
from hephae_common.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)

MAPS_MCP_URL = "https://mapstools.googleapis.com/mcp"

MAPS_GROUNDING_INSTRUCTION = """You are a competitive landscape analyst. You have access to Google Maps place search tools.

For the given location and business type, search for businesses and return a structured analysis.

Search for the primary business type first, then for related/competing categories.

Return a JSON object with:
- totalPlaces: number of places found
- categories: dict of category -> count (e.g. "restaurant": 8, "fast_food": 3)
- topPlaces: list of top 5 places by relevance [{name, rating, userRatingCount, priceLevel, types}]
- newOrNotable: any places that appear new, recently opened, or particularly notable
- saturationAssessment: "low" (<10), "moderate" (10-25), "high" (25-50), "saturated" (50+)
- summary: 1-2 sentence assessment of the competitive landscape

Return ONLY valid JSON. No markdown fencing."""


def _create_maps_toolset() -> McpToolset | None:
    """Create MCP toolset for Google Maps Grounding Lite.

    Requires GOOGLE_MAPS_API_KEY env var for authentication.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        logger.warning("[MapsGrounding] No GOOGLE_MAPS_API_KEY configured")
        return None

    try:
        toolset = McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=MAPS_MCP_URL,
                headers={"X-Goog-Api-Key": api_key},
                timeout=15.0,
            ),
            tool_filter=["search_places"],  # Only use search, not weather/routes
            tool_name_prefix="maps",
        )
        return toolset
    except Exception as e:
        logger.error(f"[MapsGrounding] Failed to create MCP toolset: {e}")
        return None


async def fetch_maps_density(
    town: str,
    state: str,
    zip_code: str,
    business_type: str,
) -> dict[str, Any]:
    """Fetch competitive landscape data via Google Maps Grounding Lite.

    Returns business density, ratings, and competitive assessment.
    """
    empty: dict[str, Any] = {}

    if not town or not os.getenv("GOOGLE_MAPS_API_KEY"):
        return empty

    try:
        toolset = _create_maps_toolset()
        if not toolset:
            return empty

        # Get tools from the MCP server
        tools = await toolset.get_tools()
        if not tools:
            logger.warning("[MapsGrounding] No tools available from MCP server")
            await toolset.close()
            return empty

        # Create agent with Maps tools
        agent = LlmAgent(
            name="maps_grounding",
            model=AgentModels.PRIMARY_MODEL,
            description="Searches Google Maps for business density analysis.",
            instruction=MAPS_GROUNDING_INSTRUCTION,
            tools=tools,
            on_model_error_callback=fallback_on_error,
        )

        prompt = f"""Analyze the competitive landscape for {business_type} in {town}, {state} (zip: {zip_code}).

Search for:
1. "{business_type} in {town} {state} {zip_code}"
2. Related business categories near {zip_code}

Provide the structured competitive analysis."""

        result = await run_agent_to_json(
            agent,
            prompt,
            app_name="maps_grounding",
        )

        await toolset.close()

        if result and isinstance(result, dict):
            result["source"] = "google_maps_grounding"
            logger.info(f"[MapsGrounding] Got {result.get('totalPlaces', 0)} places for {town}/{business_type}")
            return result

        return empty

    except Exception as e:
        logger.error(f"[MapsGrounding] Failed for {town}/{business_type}: {e}")
        return empty
