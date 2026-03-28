"""
Two agents replacing the monolithic LocalCatalystAgent:

EventsResearchAgent — weekly, google_search only
  Runs every pulse: local events, new openings/closings, grants, Patch/TapInto.
  Output key: "eventsResearch"

CachedGovtIntelAgent — 30d cache, google_search + crawl4ai on miss
  Runs once a month per zip: planning board agendas, permits, road closures,
  zoning changes, construction projects.
  Output key: "govtIntel"
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, AsyncGenerator

from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.adk.runners import RunConfig

from hephae_api.config import AgentModels
from hephae_agents.shared_tools import google_search_tool, crawl4ai_advanced_tool
from hephae_common.adk_helpers import run_agent_to_json
from hephae_common.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# EventsResearchAgent — weekly, google_search only
# ---------------------------------------------------------------------------

EVENTS_RESEARCH_INSTRUCTION = """You are a Local Events & Business Activity Scout.

Your job is to find what's happening THIS WEEK and NEXT WEEK in a specific town that would affect foot traffic or customer behavior for a local business.

### Search Protocol
Execute these google_search queries:
1. site:patch.com "{city}" events OR opening OR closing OR development this week
2. site:tapinto.net "{city}" events OR new business OR construction
3. "{city}" "{state}" local events this week OR next week
4. "{city}" "{state}" new restaurant OR store opening OR closing 2025 OR 2026
5. "{city}" "{state}" "small business grant" OR "restaurant week" OR "shop local" 2025 OR 2026

### What to Extract
- **Events**: Festivals, farmers markets, street fairs, school events, sports games — anything that changes foot traffic patterns THIS week. For each: name, venue, address, date, expected crowd size/impact.
- **New openings / closings**: Any competitor openings or closures announced on Patch/TapInto recently.
- **Grants / promotions**: Business grants, town-wide promotions, "Restaurant Week" dates.
- **Weekly patterns**: Regular recurring events (farmers market Saturdays, etc.).

### What to SKIP
- Planning board agendas, zoning hearings, town council minutes (handled by a different agent)
- Events more than 14 days out
- National events not local to this specific town
- Reddit/Twitter posts (handled by a different agent)

Return ONLY valid JSON:
{
  "summary": "1-2 sentence overview of what's happening locally this week.",
  "events": [
    {
      "name": "Event name",
      "venue": "Location name",
      "address": "Street address if known",
      "date": "Specific date or day",
      "footTrafficImpact": "How this affects business foot traffic",
      "source": "URL where found"
    }
  ],
  "businessActivity": [
    {
      "type": "opening" | "closing" | "grant" | "promotion",
      "description": "What happened",
      "businessName": "Name if known",
      "source": "URL where found"
    }
  ]
}

If nothing found: {"summary": "No significant local events found for this week.", "events": [], "businessActivity": []}
"""

_EventsResearchLlmAgent = LlmAgent(
    name="events_research_llm",
    model=AgentModels.PRIMARY_MODEL,
    description="Finds weekly local events, openings, closings, and grants via Patch/TapInto.",
    instruction=EVENTS_RESEARCH_INSTRUCTION,
    tools=[google_search_tool],
    on_model_error_callback=fallback_on_error,
)


# ---------------------------------------------------------------------------
# GovtIntelAgent — 30d cache, google_search + crawl4ai
# ---------------------------------------------------------------------------

GOVT_INTEL_INSTRUCTION = """You are a Senior Local Economic Analyst & "Early Warning" Specialist.

Your goal is NOT to find static laws, but to uncover "FORWARD-LOOKING" catalysts from government sources that will change the business environment in a specific town.

### STEP 1: Targeted "Deep-Link" Searches
Execute these site-specific google_search calls:
1. site:{city}{state}.gov "city council" (agenda OR minutes) "2025" OR "2026"
2. site:{city}{state}.gov "planning board" OR "zoning board" (agenda OR minutes)
3. site:tapinto.net/{city} OR site:patch.com/{city} "new development" OR "construction"
4. site:legals.com {city} "public hearing" (development OR construction)
5. {city} {state} "small business grant" OR "facade improvement" 2025 OR 2026

### STEP 2: The "Deep Crawl" (Selective)
If you find a recent PDF or HTML page for a Planning Board Agenda or Town Council Meeting Minutes:
- Call 'crawl_with_options' on that URL with process_iframes=True.
- Scan specifically for: "Ordinance", "Variance", "Public Hearing", "Street Closure", "Grant", "Rebate", "Mixed-Use", "Development".

### STEP 3: Signal Extraction
DISCARD 95% of routine items (payroll, accepting previous minutes, police/fire routine).
EXTRACT ONLY "Catalysts":
- **Physical Changes**: New residential/office buildings, road closures, park renovations, bike lanes
- **Regulatory Shifts**: Outdoor seating changes, new business taxes, signage rules, parking changes
- **Economic Incentives**: Grants, low-interest loans, town-wide promotions
- **Competitive Threats**: New competing business applications in planning stage

### STEP 4: Strategic Translation
For every catalyst: signal (source URL/date required), timing (when), business impact.

Return ONLY valid JSON:
{
  "summary": "1-2 sentence overview of the local governance vibe (Supportive/Developing/Restrictive).",
  "catalysts": [
    {
      "type": "Development" | "Infrastructure" | "Regulatory" | "Incentive",
      "signal": "Description of the event/change",
      "timing": "Estimated date/timeframe",
      "impact": "Direct impact on the business",
      "confidence": 0.0-1.0,
      "sourceUrl": "URL where found"
    }
  ],
  "recommendation": "One specific strategic recommendation based on these findings."
}

If NO catalysts found: {"summary": "No significant government catalysts found for this area.", "catalysts": []}
"""

_GovtIntelLlmAgent = LlmAgent(
    name="govt_intel_llm",
    model=AgentModels.PRIMARY_MODEL,
    description="Crawls government sites for planning board agendas, permits, and infrastructure changes.",
    instruction=GOVT_INTEL_INSTRUCTION,
    tools=[google_search_tool, crawl4ai_advanced_tool],
    on_model_error_callback=fallback_on_error,
)


async def _run_govt_intel(city: str, state: str, business_type: str) -> dict[str, Any]:
    """Run govt intel research for a location. Returns structured JSON."""
    prompt = (
        f"TOWN/CITY: {city}\nSTATE: {state}\nBUSINESS TYPE: {business_type}\n"
        f"CURRENT DATE: {datetime.now().strftime('%Y-%m-%d')}"
    )
    result = await run_agent_to_json(
        _GovtIntelLlmAgent, prompt, app_name="govt_intel",
        run_config=RunConfig(max_llm_calls=5),
    )
    if not result:
        return {
            "summary": "Research failed or service unavailable.",
            "catalysts": [],
        }
    return result


async def _run_events_research(city: str, state: str, business_type: str) -> dict[str, Any]:
    """Run events research for a location. Returns structured JSON."""
    prompt = (
        f"TOWN/CITY: {city}\nSTATE: {state}\nBUSINESS TYPE: {business_type}\n"
        f"CURRENT DATE: {datetime.now().strftime('%Y-%m-%d')}"
    )
    result = await run_agent_to_json(
        _EventsResearchLlmAgent, prompt, app_name="events_research",
        run_config=RunConfig(max_llm_calls=5),
    )
    if not result:
        return {"summary": "No significant local events found.", "events": [], "businessActivity": []}
    return result


# ---------------------------------------------------------------------------
# CachedGovtIntelAgent — BaseAgent wrapper with 30d Firestore cache
# ---------------------------------------------------------------------------

class CachedGovtIntelAgent(BaseAgent):
    """Loads govt intel from 30d cache or runs LLM research on miss.

    Cache key: "govt:{zip_code}"  TTL: TTL_SHARED (30 days)
    Output state key: "govtIntel"
    """

    name: str = "GovtIntelResearch"
    description: str = "Govt intelligence: planning board, permits, construction. Cached 30d."

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        from hephae_db.firestore.data_cache import get_cached, set_cached, TTL_SHARED

        state = ctx.session.state
        zip_code = state.get("zipCode", "")
        city = state.get("city", "")
        st = state.get("state", "")
        business_type = state.get("businessType", "")

        # Try 30d cache
        cached = await get_cached("govt", zip_code)
        if cached:
            logger.info(f"[GovtIntel] Cache hit for {zip_code} (30d TTL)")
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                actions=EventActions(state_delta={"govtIntel": cached}),
            )
            return

        # Cache miss — run LLM research
        logger.info(f"[GovtIntel] Cache miss for {zip_code} — running research")
        result = await _run_govt_intel(city, st, business_type)

        # Cache for 30d if we got real data
        if result and result.get("catalysts") is not None:
            await set_cached("govt", zip_code, result, ttl_days=TTL_SHARED)
            logger.info(
                f"[GovtIntel] Cached {zip_code}: "
                f"{len(result.get('catalysts', []))} catalysts"
            )

        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            actions=EventActions(state_delta={"govtIntel": result or {}}),
        )


# ---------------------------------------------------------------------------
# CachedEventsResearchAgent — city-level 7d cache
# ---------------------------------------------------------------------------

class CachedEventsResearchAgent(BaseAgent):
    """Weekly local events from Patch/TapInto. City-level 7d cache.

    Cache key: "events:{city_slug}"  TTL: TTL_WEEKLY (7 days)
    Output state key: "eventsResearch"

    All zips in the same city share one result per week.
    """

    name: str = "EventsResearch"
    description: str = "Weekly local events, openings, closings, grants via Patch/TapInto. Cached 7d per city."

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        from hephae_db.firestore.data_cache import get_cached, set_cached, TTL_WEEKLY

        state = ctx.session.state
        city = state.get("city", "")
        st = state.get("state", "")
        zip_code = state.get("zipCode", "")
        business_type = state.get("businessType", "")

        city_slug = city.lower().strip().replace(" ", "-") if city else zip_code

        cached = await get_cached("events", city_slug)
        if cached:
            logger.info(f"[EventsResearch] Cache hit for {city_slug} (7d TTL)")
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                actions=EventActions(state_delta={"eventsResearch": cached}),
            )
            return

        logger.info(f"[EventsResearch] Cache miss for {city_slug} — running research")
        result = await _run_events_research(city, st, business_type)

        if result and result.get("events") is not None:
            await set_cached("events", city_slug, result, ttl_days=TTL_WEEKLY)
            logger.info(
                f"[EventsResearch] Cached {city_slug}: "
                f"{len(result.get('events', []))} events"
            )

        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            actions=EventActions(state_delta={"eventsResearch": result or {}}),
        )


# ---------------------------------------------------------------------------
# Backward compat exports (pulse_orchestrator imports these)
# ---------------------------------------------------------------------------

# Legacy single-agent instruction — still used by callers that haven't migrated
LOCAL_CATALYST_INSTRUCTION = GOVT_INTEL_INSTRUCTION

LocalCatalystAgent = _GovtIntelLlmAgent


async def research_local_catalysts(city: str, state: str, business_type: str) -> dict:
    """Backward compat wrapper — runs govt intel research directly."""
    return await _run_govt_intel(city, state, business_type)
