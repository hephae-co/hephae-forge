"""Business Overview runner — Google Search + Maps Grounding + Zipcode/Pulse data.

Lightweight but data-rich overview for the chatbot landing experience.
Runs Google Search + Maps agents in parallel with Firestore data loads,
then synthesizes into a structured business overview.

Expected latency: ~8-12 seconds.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import json
import uuid

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.runners import RunConfig, Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import google_search

from hephae_common.adk_helpers import user_msg
from hephae_common.model_config import AgentModels
from hephae_common.model_fallback import fallback_on_error

from hephae_agents.business_overview.agent import (
    SEARCH_INSTRUCTION,
    MAPS_INSTRUCTION,
    SYNTHESIZER_INSTRUCTION,
)

logger = logging.getLogger(__name__)


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


async def _load_zipcode_profile(zip_code: str) -> dict[str, Any] | None:
    """Load zipcode profile (discovered data sources) from Firestore."""
    if not zip_code:
        return None

    try:
        from hephae_db.firestore.zipcode_profiles import get_zipcode_profile

        profile = await get_zipcode_profile(zip_code)
        if not profile:
            return None

        # Extract compact summary for the synthesizer
        sources = profile.get("sources", {})
        census = sources.get("census_acs", {})
        osm = sources.get("osm_businesses", {})

        return {
            "city": profile.get("city"),
            "state": profile.get("state"),
            "county": profile.get("county"),
            "confirmedSources": profile.get("confirmedSources", 0),
            "census": census.get("note", ""),
            "osmNote": osm.get("note", ""),
            "localNewspaper": sources.get("local_newspaper", {}).get("url"),
            "chamberOfCommerce": sources.get("chamber_of_commerce", {}).get("url"),
            "patchUrl": sources.get("patch_com", {}).get("url"),
            "schoolDistrict": sources.get("school_district", {}).get("url"),
            "librarySystem": sources.get("library_system", {}).get("url"),
        }
    except Exception as e:
        logger.warning(f"[BusinessOverview] Zipcode profile load failed: {e}")
        return None


async def _load_osm_competitors(latitude: float, longitude: float, business_type: str) -> list[dict[str, Any]]:
    """Load nearby competitors from OSM via BigQuery (with lat/lng for map pins)."""
    if not latitude or not longitude:
        return []

    try:
        from hephae_db.bigquery.public_data import query_osm_business_density

        result = await query_osm_business_density(latitude, longitude, business_type)
        return result.get("nearby", []) if result else []
    except Exception as e:
        logger.warning(f"[BusinessOverview] OSM competitors load failed: {e}")
        return []


async def _load_latest_pulse(zip_code: str, business_type: str) -> dict[str, Any] | None:
    """Load the latest weekly pulse for this zip + business type."""
    if not zip_code:
        return None

    try:
        from hephae_db.firestore.weekly_pulse import get_latest_pulse

        pulse = await get_latest_pulse(zip_code, business_type or "Restaurants")
        if not pulse:
            return None

        pulse_data = pulse.get("pulse", {})
        insights = pulse_data.get("insights", [])
        local_briefing = pulse_data.get("localBriefing", {})

        return {
            "headline": pulse_data.get("headline", ""),
            "weekOf": pulse.get("weekOf", ""),
            "topInsights": [
                {"title": i.get("title", ""), "recommendation": i.get("recommendation", "")}
                for i in insights[:3]
            ],
            "events": (local_briefing.get("thisWeekInTown", []) if isinstance(local_briefing, dict) else [])[:3],
            "communityBuzz": local_briefing.get("communityBuzz", "") if isinstance(local_briefing, dict) else "",
            "competitorWatch": local_briefing.get("competitorWatch", []) if isinstance(local_briefing, dict) else [],
        }
    except Exception as e:
        logger.warning(f"[BusinessOverview] Pulse load failed: {e}")
        return None


def _build_dashboard(
    zipcode_profile: dict[str, Any] | None,
    pulse_data: dict[str, Any] | None,
    osm_competitors: list[dict[str, Any]],
    latitude: float,
    longitude: float,
) -> dict[str, Any]:
    """Build compact dashboard payload for the frontend map + stat cards."""
    dashboard: dict[str, Any] = {
        "businessLocation": {"lat": latitude, "lng": longitude} if latitude and longitude else None,
        "competitors": osm_competitors[:10],
        "stats": {},
        "events": [],
        "communityBuzz": None,
        "pulseHeadline": None,
        "topInsights": [],
        "confirmedSources": 0,
    }

    if zipcode_profile:
        dashboard["confirmedSources"] = zipcode_profile.get("confirmedSources", 0)
        census_note = zipcode_profile.get("census", "")
        # Parse "pop=28428, income=$95,259" from census note
        if census_note:
            import re
            pop_match = re.search(r'pop=([0-9,]+)', census_note)
            inc_match = re.search(r'income=\$([0-9,]+)', census_note)
            dashboard["stats"]["population"] = pop_match.group(1) if pop_match else None
            dashboard["stats"]["medianIncome"] = f"${inc_match.group(1)}" if inc_match else None
        dashboard["stats"]["city"] = zipcode_profile.get("city")
        dashboard["stats"]["state"] = zipcode_profile.get("state")
        dashboard["stats"]["county"] = zipcode_profile.get("county")
        dashboard["stats"]["localNewspaper"] = zipcode_profile.get("localNewspaper")
        dashboard["stats"]["patchUrl"] = zipcode_profile.get("patchUrl")

    dashboard["stats"]["competitorCount"] = len(osm_competitors)

    if pulse_data:
        dashboard["pulseHeadline"] = pulse_data.get("headline")
        dashboard["events"] = pulse_data.get("events", [])[:5]
        dashboard["communityBuzz"] = pulse_data.get("communityBuzz")
        dashboard["topInsights"] = pulse_data.get("topInsights", [])[:3]

    return dashboard


async def run_business_overview(identity: dict[str, Any]) -> dict[str, Any]:
    """Run business overview with Google Search + Maps + Zipcode/Pulse data.

    Returns structured overview with businessSnapshot, marketPosition,
    localEconomy, localBuzz, keyOpportunities, capabilityTeasers.
    """
    name = identity.get("name", "Unknown")
    address = identity.get("address", "")
    zip_code = identity.get("zipCode", "")
    business_type = identity.get("businessType", "Restaurants")
    coords = identity.get("coordinates", {}) or {}
    latitude = coords.get("lat", 0)
    longitude = coords.get("lng", 0)

    logger.info(f"[BusinessOverview] Starting overview for: {name} ({zip_code})")

    # Load all data sources in parallel
    zipcode_context, zipcode_profile, pulse_data, osm_competitors = await asyncio.gather(
        _load_zipcode_context(zip_code),
        _load_zipcode_profile(zip_code),
        _load_latest_pulse(zip_code, business_type),
        _load_osm_competitors(latitude, longitude, business_type),
    )

    logger.info(
        f"[BusinessOverview] Data loaded — context: {bool(zipcode_context)}, "
        f"profile: {bool(zipcode_profile)}, pulse: {bool(pulse_data)}"
    )

    # --- Build ADK agents ---

    # Sub-agent 1: Google Search Research
    search_agent = LlmAgent(
        name="overview_search",
        model=AgentModels.PRIMARY_MODEL,
        description="Searches Google for business information and local trends.",
        instruction=SEARCH_INSTRUCTION,
        tools=[google_search],
        output_key="searchResults",
        on_model_error_callback=fallback_on_error,
    )

    # Sub-agent 2: Competitor researcher — uses Google Search grounding
    # (OSM competitor data is already loaded in zipcodeProfile from Firestore)
    competitor_agent = LlmAgent(
        name="overview_competitors",
        model=AgentModels.PRIMARY_MODEL,
        description="Researches nearby competitors via Google Search.",
        instruction=MAPS_INSTRUCTION,
        tools=[google_search],
        output_key="mapsData",
        on_model_error_callback=fallback_on_error,
    )

    # Parallel research phase — both use Google Search grounding
    research_phase = ParallelAgent(
        name="overview_research",
        description="Parallel business + competitor research.",
        sub_agents=[search_agent, competitor_agent],
    )

    # Synthesizer — reads all data from state
    synthesizer = LlmAgent(
        name="overview_synthesizer",
        model=AgentModels.PRIMARY_MODEL,
        description="Synthesizes research into a structured business overview.",
        instruction=SYNTHESIZER_INSTRUCTION,
        output_key="overview",
        on_model_error_callback=fallback_on_error,
    )

    # Sequential: research → synthesize
    pipeline = SequentialAgent(
        name="business_overview_pipeline",
        description="Business overview pipeline.",
        sub_agents=[research_phase, synthesizer],
    )

    # Build prompt
    prompt = f"""Analyze the business: {name}
Location: {address}
Zip Code: {zip_code}
Business Type: {business_type}

Search for this business and its competitors in the area."""

    # Build initial state with all loaded data
    initial_state = {
        "businessName": name,
        "businessAddress": address,
        "zipCode": zip_code,
        "businessType": business_type,
        "zipcodeContext": zipcode_context,
        "zipcodeProfile": zipcode_profile,
        "latestPulse": pulse_data,
    }

    try:
        session_service = InMemorySessionService()
        session_id = f"overview-{uuid.uuid4().hex[:8]}"
        session = await session_service.create_session(
            app_name="business_overview",
            session_id=session_id,
            user_id="system",
            state=initial_state,
        )

        runner = Runner(
            agent=pipeline,
            app_name="business_overview",
            session_service=session_service,
        )

        last_text = ""
        async for event in runner.run_async(
            user_id="system",
            session_id=session.id,
            new_message=user_msg(prompt),
            run_config=RunConfig(max_llm_calls=8),
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        last_text = part.text

        if not last_text:
            # Try reading the overview from session state
            final_session = await session_service.get_session(
                app_name="business_overview",
                session_id=session.id,
                user_id="system",
            )
            if final_session and final_session.state:
                overview = final_session.state.get("overview", "")
                if overview and isinstance(overview, str):
                    last_text = overview

        # Build curated dashboard payload (compact, for frontend map + stats)
        dashboard = _build_dashboard(
            zipcode_profile, pulse_data, osm_competitors,
            latitude, longitude,
        )

        # Parse JSON from the last text output
        if last_text:
            try:
                result = json.loads(last_text)
                if isinstance(result, dict):
                    result["dashboard"] = dashboard
                    logger.info(f"[BusinessOverview] Overview complete for: {name}")
                    return result
            except json.JSONDecodeError:
                import re
                match = re.search(r'```(?:json)?\s*([\s\S]*?)```', last_text)
                if match:
                    try:
                        result = json.loads(match.group(1))
                        if isinstance(result, dict):
                            result["dashboard"] = dashboard
                            return result
                    except json.JSONDecodeError:
                        pass
                return {"summary": last_text[:500], "dashboard": dashboard}

        logger.warning(f"[BusinessOverview] No output for: {name}")
        return {"summary": f"Overview for {name} is being prepared.", "error": "incomplete"}

    except Exception as e:
        logger.error(f"[BusinessOverview] Pipeline failed for {name}: {e}")
        return {"summary": f"Unable to generate overview for {name}.", "error": str(e)}

    finally:
        pass
