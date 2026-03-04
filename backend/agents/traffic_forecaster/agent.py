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

from backend.config import AgentModels
from backend.lib.model_fallback import fallback_on_error, generate_with_fallback
from backend.agents.shared_tools import google_search_tool
from backend.agents.traffic_forecaster.prompts import (
    POI_GATHERER_INSTRUCTION,
    WEATHER_GATHERER_INSTRUCTION,
    EVENTS_GATHERER_INSTRUCTION,
)
from backend.agents.traffic_forecaster.tools import weather_tool
from backend.lib.adk_helpers import user_msg

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


class ForecasterAgent:
    @staticmethod
    async def forecast(identity: dict[str, Any]) -> dict[str, Any]:
        """Run the full traffic forecasting pipeline."""
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

        session_service = InMemorySessionService()
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
                temperature=0.2,
            ),
        )

        text = response.text
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            logger.error(f"[ForecasterAgent] Failed to parse Synthesis Output: {text}")
            raise ValueError("Forecaster API returned malformed JSON.")
