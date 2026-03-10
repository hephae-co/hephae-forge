"""
MunicipalHubAgent — finds high-trust directory URLs (Chamber of Commerce, Town Registry).

Used to discover local businesses without relying on expensive broad grounding.
"""

from __future__ import annotations

import logging
from google.adk.agents import LlmAgent
from backend.config import AgentModels
from hephae_common.adk_helpers import run_agent_to_text
from hephae_capabilities.shared_tools import google_search_tool
from hephae_common.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)

HUB_FINDER_INSTRUCTION = """You are a Local Research Specialist.
Your job is to find the single most authoritative "Business Directory" URL for a specific town or city.

PRIORITY ORDER:
1. Official Chamber of Commerce Member Directory (e.g., "montclairchamber.com/directory")
2. Municipal/Township Business Registry (.gov or .org)
3. Local Business Association List (e.g., "Main Street Association")

EXCLUDE: Yelp, YellowPages, Groupon, Tripadvisor, or any other non-local aggregate sites.

Return ONLY the direct URL to the directory search or listing page. If you find multiple, return the most official one.
If no official directory is found, return "NONE"."""

MunicipalHubAgent = LlmAgent(
    name="municipal_hub_finder",
    model=AgentModels.PRIMARY_MODEL,
    instruction=HUB_FINDER_INSTRUCTION,
    tools=[google_search_tool],
    on_model_error_callback=fallback_on_error,
)

async def find_municipal_hub(city: str, state: str) -> str | None:
    """Find the authoritative directory URL for a city."""
    prompt = f"Find the official Chamber of Commerce or Municipal business directory for {city}, {state}."
    url = await run_agent_to_text(MunicipalHubAgent, prompt, app_name="hub_finder")
    if url and url.strip().upper() != "NONE" and url.startswith("http"):
        return url.strip()
    return None
