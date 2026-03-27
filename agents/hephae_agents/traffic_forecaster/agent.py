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

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.apps.app import App
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from hephae_common.model_config import AgentModels, ThinkingPresets
from hephae_common.model_fallback import fallback_on_error
from google.adk.tools import google_search
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
    tools=[google_search],
    output_key="poiDetails",
    on_model_error_callback=fallback_on_error,
)

weather_gatherer = LlmAgent(
    name="WeatherGatherer",
    model=AgentModels.PRIMARY_MODEL,
    instruction=WEATHER_GATHERER_INSTRUCTION,
    tools=[weather_tool, google_search],
    output_key="weatherData",
    on_model_error_callback=fallback_on_error,
)

events_gatherer = LlmAgent(
    name="EventsGatherer",
    model=AgentModels.PRIMARY_MODEL,
    instruction=EVENTS_GATHERER_INSTRUCTION,
    tools=[google_search],
    output_key="eventsData",
    on_model_error_callback=fallback_on_error,
)

context_gathering_pipeline = ParallelAgent(
    name="ContextGatherer",
    description="Gathers POIs, Weather, and Events in parallel.",
    sub_agents=[poi_gatherer, weather_gatherer, events_gatherer],
)

_FORECAST_CACHE_CONFIG = ContextCacheConfig(
    min_tokens=1024,
    ttl_seconds=600,
    cache_intervals=20,
)

_context_gathering_app = App(
    name="hephae_forecast_context",
    root_agent=context_gathering_pipeline,
    context_cache_config=_FORECAST_CACHE_CONFIG,
)


def _synthesis_instruction(ctx) -> str:
    """Build synthesis instruction from session state — injects all gathered intelligence."""
    state = getattr(ctx, "state", {})
    poi_details = state.get("poiDetails", "No POI data found.")
    weather_data = state.get("weatherData", "No weather data found.")
    events_data = state.get("eventsData", "No events data found.")
    admin_context = state.get("adminContext", "No additional admin research data available.")
    name = state.get("businessName", "Unknown")
    address = state.get("businessAddress", "")
    lat = state.get("lat", 0)
    lng = state.get("lng", 0)
    date_string = state.get("dateString", "")

    return f"""You are an expert Local Foot Traffic Forecaster generating strict JSON based on Intelligence Data.

CURRENT DATE: {date_string}

Your task is to generate exactly a 3-day foot traffic forecast based STRICTLY on the gathered intelligence below for {name}. Never return more than 3 days in the array.

### 1. BUSINESS INTELLIGENCE
{poi_details}

### 2. WEATHER INTELLIGENCE
{weather_data}

### 3. EVENT INTELLIGENCE
{events_data}

### 4. ADMIN RESEARCH CONTEXT (if available)
{admin_context}

ANALYSIS RULES (MUST follow in order):
1. HOURS: If the business is CLOSED, Traffic Level MUST be "Closed".
2. WEATHER — CHECK BOTH SOURCES: Read Section 2 (real-time weather) AND Section 4 (admin research context). If EITHER source mentions storms, severe weather, temperature drops, or hazardous conditions for ANY forecast day, you MUST reflect that in the weatherNote AND reduce traffic scores for that day.
3. EVENTS & DISTANCE: Major nearby events boost traffic scores significantly.

Business name: {name}
Business address: {address}
Coordinates: lat={lat}, lng={lng}

Keep all text fields SHORT — bullet-style, no paragraphs."""


synthesis_agent = LlmAgent(
    name="ForecastSynthesizer",
    model=AgentModels.PRIMARY_MODEL,
    generate_content_config=ThinkingPresets.HIGH,
    description="Synthesizes POI, weather, and event intelligence into a 3-day foot traffic forecast.",
    instruction=_synthesis_instruction,
    output_schema=TrafficForecastOutput,
    output_key="forecastResult",
    on_model_error_callback=fallback_on_error,
)

forecast_pipeline = SequentialAgent(
    name="ForecastPipeline",
    description="Gathers context then synthesizes a 3-day foot traffic forecast.",
    sub_agents=[context_gathering_pipeline, synthesis_agent],
)

_forecast_pipeline_app = App(
    name="hephae_forecast",
    root_agent=forecast_pipeline,
    context_cache_config=_FORECAST_CACHE_CONFIG,
)


def _build_admin_context(business_context: Any, identity: dict[str, Any] | None = None) -> str:
    """Build additional context from admin research data for synthesis.

    Checks two sources:
    1. BusinessContext object (from build_business_context)
    2. Identity dict keys (zipCodeResearchContext, areaResearchContext) — set by workflow analysis
    """
    parts: list[str] = []

    # Source 1: BusinessContext object
    if business_context and getattr(business_context, "has_admin_data", False):
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

    # Source 2: Identity dict (workflow analysis embeds research here)
    if not parts and identity:
        zrc = identity.get("zipCodeResearchContext")
        if zrc and isinstance(zrc, dict):
            if zrc.get("demographics"):
                parts.append(f"**Demographics**: {zrc['demographics'][:2000]}")
            if zrc.get("events"):
                parts.append(f"**Local Events (Admin)**: {zrc['events'][:2000]}")
            if zrc.get("weather"):
                parts.append(f"**Seasonal Weather**: {zrc['weather'][:1500]}")

        arc = identity.get("areaResearchContext")
        if arc and isinstance(arc, dict):
            summary = arc.get("summary", {})
            if isinstance(summary, dict):
                if summary.get("marketOpportunity"):
                    parts.append(f"**Market Opportunity**: {json.dumps(summary['marketOpportunity'], default=str)[:1000]}")
                if summary.get("competitiveLandscape"):
                    parts.append(f"**Competitive Landscape**: {json.dumps(summary['competitiveLandscape'], default=str)[:1000]}")

    return "\n".join(parts) if parts else "No additional admin research data available."


class ForecasterAgent:
    @staticmethod
    async def forecast(identity: dict[str, Any], business_context: Any = None, skip_synthesis: bool = False, **kwargs) -> dict[str, Any]:
        """Run the full traffic forecasting pipeline.

        Args:
            identity: Enriched identity dict.
            business_context: Optional BusinessContext with admin data for richer synthesis.
            skip_synthesis: If True, run gathering only and return deferred intel data.
        """
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

        address = identity.get("address", "")
        initial_state = {
            "businessName": name,
            "businessAddress": address,
            "lat": lat,
            "lng": lng,
            "dateString": date_string,
            "locationQuery": location_query,
            "adminContext": _build_admin_context(business_context, identity),
        }

        session_service = InMemorySessionService()
        session_id = f"forecast-{int(time.time() * 1000)}"
        await session_service.create_session(
            app_name="hephae_forecast_context",
            session_id=session_id,
            user_id="sys",
            state=initial_state,
        )

        prompt = (
            f"Business: {name}\n"
            f"Location: {location_query}\n"
            f"Latitude: {lat}\nLongitude: {lng}\n"
            f"Today: {date_string}\n\n"
            "Please gather intelligence context."
        )

        if skip_synthesis:
            # Run only context gathering pipeline
            context_runner = Runner(app=_context_gathering_app, session_service=session_service)
            async for _ in context_runner.run_async(
                session_id=session_id,
                user_id="sys",
                new_message=user_msg(prompt),
            ):
                pass

            final_session = await session_service.get_session(
                app_name="hephae_forecast_context", session_id=session_id, user_id="sys"
            )
            state = final_session.state if final_session else {}
            return {
                "deferred": True,
                "intel": {
                    "poi": state.get("poiDetails", "No POI data found."),
                    "weather": state.get("weatherData", "No weather data found."),
                    "events": state.get("eventsData", "No events data found."),
                },
                "identity": identity,
                "business_context_summary": initial_state["adminContext"],
            }

        # Run full pipeline (context gathering + synthesis)
        logger.info("[ForecasterAgent] Running full forecast pipeline...")
        await session_service.create_session(
            app_name="hephae_forecast",
            session_id=session_id,
            user_id="sys",
            state=initial_state,
        )
        pipeline_runner = Runner(app=_forecast_pipeline_app, session_service=session_service)
        async for _ in pipeline_runner.run_async(
            session_id=session_id,
            user_id="sys",
            new_message=user_msg(prompt),
        ):
            pass

        final_session = await session_service.get_session(
            app_name="hephae_forecast", session_id=session_id, user_id="sys"
        )
        state = final_session.state if final_session else {}
        forecast_result = state.get("forecastResult")

        if forecast_result is None:
            logger.error("[ForecasterAgent] No forecastResult in final session state")
            raise ValueError("Forecaster pipeline returned no result.")

        if isinstance(forecast_result, str):
            try:
                return json.loads(forecast_result)
            except (json.JSONDecodeError, ValueError):
                logger.error(f"[ForecasterAgent] Failed to parse forecastResult: {forecast_result[:500]}")
                raise ValueError("Forecaster pipeline returned malformed JSON.")

        if hasattr(forecast_result, "model_dump"):
            return forecast_result.model_dump()

        return forecast_result
