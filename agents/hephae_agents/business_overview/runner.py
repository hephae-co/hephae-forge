"""Business Overview runner — Google Search + Maps Grounding Lite → Synthesis.

Lightweight alternative to the full discovery pipeline. Runs two parallel
research agents (Google Search + Maps Grounding) then synthesizes into a
quick business overview. Expected latency: ~5-8 seconds.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.runners import RunConfig
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from google.genai import types

from hephae_common.adk_helpers import run_agent_to_json
from hephae_common.model_config import AgentModels
from hephae_common.model_fallback import fallback_on_error

from hephae_agents.business_overview.agent import (
    SEARCH_INSTRUCTION,
    MAPS_INSTRUCTION,
    SYNTHESIZER_INSTRUCTION,
)

logger = logging.getLogger(__name__)

MAPS_MCP_URL = "https://mapstools.googleapis.com/mcp"


async def _load_zipcode_context(zip_code: str) -> dict[str, Any]:
    """Load zipcode research and area research from Firestore."""
    context: dict[str, Any] = {}
    if not zip_code:
        return context

    try:
        from hephae_db.context.admin_data import (
            get_zipcode_report,
            get_area_research_for_zip,
        )

        zip_report = await get_zipcode_report(zip_code)
        if zip_report:
            # Extract key fields, skip large blobs
            context["zipcodeResearch"] = {
                k: zip_report[k]
                for k in ("summary", "demographics", "economicProfile", "businessLandscape", "zipCode", "city", "state")
                if k in zip_report
            }

        area_report = await get_area_research_for_zip(zip_code)
        if area_report:
            context["areaResearch"] = {
                k: area_report[k]
                for k in ("summary", "marketOverview", "competitiveLandscape", "consumerProfile")
                if k in area_report
            }
    except Exception as e:
        logger.warning(f"[BusinessOverview] Zipcode context load failed: {e}")

    return context


async def run_business_overview(identity: dict[str, Any]) -> dict[str, Any]:
    """Run lightweight business overview using Google Search + Maps Grounding.

    Args:
        identity: BaseIdentity dict with name, address, zipCode, coordinates, etc.

    Returns:
        Overview dict with summary, footTrafficInsight, localMarketContext,
        competitiveLandscape, keyOpportunities.
    """
    name = identity.get("name", "Unknown")
    address = identity.get("address", "")
    zip_code = identity.get("zipCode", "")

    logger.info(f"[BusinessOverview] Starting overview for: {name}")

    # Load zipcode context
    zipcode_context = await _load_zipcode_context(zip_code)

    # --- Build agents ---

    # Sub-agent 1: Google Search Research
    search_agent = LlmAgent(
        name="overview_search",
        model=AgentModels.PRIMARY_MODEL,
        description="Searches Google for business information and local trends.",
        instruction=SEARCH_INSTRUCTION,
        tools=[types.Tool(google_search=types.GoogleSearch())],
        output_key="searchResults",
        on_model_error_callback=fallback_on_error,
    )

    # Sub-agent 2: Maps Grounding Lite
    maps_tools = []
    maps_toolset = None
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if api_key:
        try:
            maps_toolset = McpToolset(
                connection_params=StreamableHTTPConnectionParams(
                    url=MAPS_MCP_URL,
                    headers={"X-Goog-Api-Key": api_key},
                    timeout=15.0,
                ),
                tool_filter=["search_places"],
                tool_name_prefix="maps",
            )
            maps_tools = await maps_toolset.get_tools()
        except Exception as e:
            logger.warning(f"[BusinessOverview] Maps MCP init failed: {e}")

    maps_agent = LlmAgent(
        name="overview_maps",
        model=AgentModels.PRIMARY_MODEL,
        description="Searches Google Maps for nearby competitors and business density.",
        instruction=MAPS_INSTRUCTION,
        tools=maps_tools,
        output_key="mapsData",
        on_model_error_callback=fallback_on_error,
    )

    # Parallel research phase
    research_phase = ParallelAgent(
        name="overview_research",
        description="Parallel Google Search + Maps research.",
        sub_agents=[search_agent, maps_agent],
    )

    # Synthesizer — reads searchResults + mapsData from state
    synthesizer = LlmAgent(
        name="overview_synthesizer",
        model=AgentModels.PRIMARY_MODEL,
        description="Synthesizes research into a business overview.",
        instruction=SYNTHESIZER_INSTRUCTION,
        output_key="overview",
        on_model_error_callback=fallback_on_error,
    )

    # Sequential: research → synthesize
    pipeline = SequentialAgent(
        name="business_overview_pipeline",
        description="Lightweight business overview pipeline.",
        sub_agents=[research_phase, synthesizer],
    )

    # Build prompt
    prompt = f"""Analyze the business: {name}
Location: {address}
Zip Code: {zip_code}

Search for this business and its competitors in the area."""

    # Build initial state with zipcode context
    initial_state = {
        "businessName": name,
        "businessAddress": address,
        "zipCode": zip_code,
        "zipcodeContext": zipcode_context,
    }

    try:
        result = await run_agent_to_json(
            pipeline,
            prompt,
            app_name="business_overview",
            state=initial_state,
            run_config=RunConfig(max_llm_calls=8),
        )

        if result and isinstance(result, dict):
            logger.info(f"[BusinessOverview] Overview complete for: {name}")
            return result

        logger.warning(f"[BusinessOverview] No structured result for: {name}")
        return {"summary": f"Overview for {name} is being prepared.", "error": "incomplete"}

    except Exception as e:
        logger.error(f"[BusinessOverview] Pipeline failed for {name}: {e}")
        return {"summary": f"Unable to generate overview for {name}.", "error": str(e)}

    finally:
        if maps_toolset:
            try:
                await maps_toolset.close()
            except Exception:
                pass
