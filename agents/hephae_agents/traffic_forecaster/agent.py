"""
ForecasterAgent — 3-day foot traffic forecasting with parallel intelligence gathering.
Port of src/agents/traffic-forecaster/forecaster.ts.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from typing import Any

from google import genai as genai_client_mod
from google.genai import types as genai_types

from google.adk.agents import LlmAgent, ParallelAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from hephae_common.model_config import AgentModels
from hephae_common.model_fallback import fallback_on_error, generate_with_fallback
from hephae_agents.shared_tools import google_search_tool
from hephae_agents.traffic_forecaster.prompts import (
    POI_GATHERER_INSTRUCTION,
    WEATHER_GATHERER_INSTRUCTION,
    EVENTS_GATHERER_INSTRUCTION,
)
from hephae_agents.traffic_forecaster.tools import weather_tool
from hephae_common.adk_helpers import user_msg
from hephae_db.schemas.agent_outputs import TrafficForecastOutput

logger = logging.getLogger(__name__)

# Sub-agents
poi_gatherer = LlmAgent(
    name="PoiGatherer",
    model=AgentModels.PRIMARY_MODEL,
    instruction=POI_GATHERER_INSTRUCTION,
    tools=[google_search_tool],
    output_key="poiDetails",
    on_model_error_callback=fallback_on_error,
)

weather_gatherer = LlmAgent(
    name="WeatherGatherer",
    model=AgentModels.PRIMARY_MODEL,
    instruction=WEATHER_GATHERER_INSTRUCTION,
    tools=[weather_tool, google_search_tool],
    output_key="weatherData",
    on_model_error_callback=fallback_on_error,
)

events_gatherer = LlmAgent(
    name="EventsGatherer",
    model=AgentModels.PRIMARY_MODEL,
    instruction=EVENTS_GATHERER_INSTRUCTION,
    tools=[google_search_tool],
    output_key="eventsData",
    on_model_error_callback=fallback_on_error,
)

context_gathering_pipeline = ParallelAgent(
    name="ContextGatherer",
    description="Gathers POIs, Weather, and Events in parallel.",
    sub_agents=[poi_gatherer, weather_gatherer, events_gatherer],
)


def _build_admin_context(business_context: Any) -> str:
    """Build additional context from admin research data for synthesis."""
    if not business_context or not getattr(business_context, "has_admin_data", False):
        return "No additional admin research data available."

    parts = []
    zr = getattr(business_context, "zipcode_research", None)
    if zr and isinstance(zr, dict):
        sections = zr.get("sections", {})
        if isinstance(sections, dict):
            if sections.get("demographics"):
                parts.append(f"**Demographics**: {json.dumps(sections['demographics'], default=str)[:2000]}")
            if sections.get("events"):
                parts.append(f"**Local Events (Admin)**: {json.dumps(sections['events'], default=str)[:2000]}")
            if sections.get("seasonal_weather"):
                parts.append(f"**Seasonal Weather**: {json.dumps(sections['seasonal_weather'], default=str)[:1500]}")
            if sections.get("consumer_market"):
                parts.append(f"**Consumer Market**: {json.dumps(sections['consumer_market'], default=str)[:1500]}")

    ar = getattr(business_context, "area_research", None)
    if ar and isinstance(ar, dict):
        if ar.get("marketOpportunity"):
            parts.append(f"**Market Opportunity**: {json.dumps(ar['marketOpportunity'], default=str)[:1000]}")
        if ar.get("competitiveLandscape"):
            parts.append(f"**Competitive Landscape**: {json.dumps(ar['competitiveLandscape'], default=str)[:1000]}")

    return "\n".join(parts) if parts else "No additional admin research data available."


class ForecasterAgent:
    @staticmethod
    async def forecast(identity: dict[str, Any], business_context: Any = None, **kwargs) -> dict[str, Any]:
        """Run the full traffic forecasting pipeline.

        Args:
            identity: Enriched identity dict.
            business_context: Optional BusinessContext with admin data for richer synthesis.
        """
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Missing GEMINI_API_KEY")

        name = identity.get("name", "Unknown")
        logger.info(f"[ForecasterAgent] Gathering Intelligence via ParallelAgent for: {name}...")

        today = datetime.now()
        date_string = today.strftime("%A, %B %d, %Y")
        location_query = identity.get("address") or ""
        coords = identity.get("coordinates") or {}
        lat = coords.get("lat", 0)
        lng = coords.get("lng", 0)

        if not location_query and (lat and lng):
            location_query = f"{lat}, {lng}"

        session_service = (kwargs or {}).get("session_service") or InMemorySessionService()
        runner = Runner(
            app_name="hephae-hub",
            agent=context_gathering_pipeline,
            session_service=session_service,
        )

        session_id = f"forecast-{int(time.time() * 1000)}"
        await session_service.create_session(
            app_name="hephae-hub", session_id=session_id, user_id="sys", state={}
        )

        prompt = (
            f"Business: {name}\n"
            f"Location: {location_query}\n"
            f"Latitude: {lat}\nLongitude: {lng}\n"
            f"Today: {date_string}\n\n"
            "Please gather intelligence context."
        )

        async for _ in runner.run_async(
            session_id=session_id,
            user_id="sys",
            new_message=user_msg(prompt),
        ):
            pass

        final_session = await session_service.get_session(
            app_name="hephae-hub", session_id=session_id, user_id="sys"
        )
        state = final_session.state if final_session else {}

        poi_details = state.get("poiDetails", "No POI data found.")
        weather_data = state.get("weatherData", "No weather data found.")
        events_data = state.get("eventsData", "No events data found.")

        # Synthesis
        logger.info("[ForecasterAgent] Intelligence gathered. Synthesizing report...")
        synthesis_client = genai_client_mod.Client(api_key=api_key)

        address = identity.get("address", "")
        analyst_prompt = f"""
      **CURRENT DATE**: {date_string}

      Your task is to generate exactly a 3-day foot traffic forecast based STRICTLY on the gathered intelligence below for {name}. Never return more than 3 days in the array.

      ### 1. BUSINESS INTELLIGENCE
      {poi_details}

      ### 2. WEATHER INTELLIGENCE
      {weather_data}

      ### 3. EVENT INTELLIGENCE
      {events_data}

      ### 4. ADMIN RESEARCH CONTEXT (if available)
      {_build_admin_context(business_context)}

      **ANALYSIS RULES**:
      1. **HOURS**: If the business is CLOSED, Traffic Level MUST be "Closed".
      2. **WEATHER**: If Severe Weather is detected, REDUCE traffic scores.
      3. **EVENTS & DISTANCE**: Major nearby events boost traffic scores significantly.

      **OUTPUT**:
      Return ONLY valid JSON matching this structure perfectly. Do not include markdown ```json blocks.
      {{
        "business": {{
          "name": "{name}",
          "address": "{address}",
          "coordinates": {{ "lat": {lat}, "lng": {lng} }},
          "type": "String",
          "nearbyPOIs": [
              {{ "name": "String", "lat": 0, "lng": 0, "type": "String" }}
          ]
        }},
        "summary": "Executive summary of the week.",
        "forecast": [
          {{
            "date": "YYYY-MM-DD",
            "dayOfWeek": "String",
            "localEvents": ["String"],
            "weatherNote": "String",
            "slots": [
               {{ "label": "Morning", "score": 0, "level": "Low/Medium/High/Closed", "reason": "String" }},
               {{ "label": "Lunch", "score": 0, "level": "Low/Medium/High/Closed", "reason": "String" }},
               {{ "label": "Afternoon", "score": 0, "level": "Low/Medium/High/Closed", "reason": "String" }},
               {{ "label": "Evening", "score": 0, "level": "Low/Medium/High/Closed", "reason": "String" }}
            ]
          }}
        ]
      }}
    """

        response = await generate_with_fallback(
            synthesis_client,
            model=AgentModels.PRIMARY_MODEL,
            contents=analyst_prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction="You are an expert Local Foot Traffic Forecaster generating strict JSON based on Intelligence Data.",
                response_mime_type="application/json",
                response_schema=TrafficForecastOutput,
                temperature=0.2,
            ),
        )

        text = response.text
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            logger.error(f"[ForecasterAgent] Failed to parse Synthesis Output: {text}")
            raise ValueError("Forecaster API returned malformed JSON.")
