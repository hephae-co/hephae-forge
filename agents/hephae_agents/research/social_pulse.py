"""Social Pulse — community sentiment via Reddit and Twitter/X only.

Searches Reddit and Twitter/X for what locals are saying about the area.
Patch and TapInto are handled by EventsResearchAgent (they are factual
event/news sources, not sentiment sources).

Cached at city level with TTL_WEEKLY (7 days). All zips in the same city
share one result per week.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, AsyncGenerator

from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.adk.runners import RunConfig
from google.adk.tools import google_search

from hephae_common.model_config import AgentModels
from hephae_common.adk_helpers import run_agent_to_text
from hephae_common.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)

# Reddit + Twitter/X only — Patch/TapInto belong in EventsResearchAgent
SOCIAL_PULSE_QUERIES = [
    'site:reddit.com/r/{state_sub} "{town}" new business OR closing OR opening OR construction OR development',
    'site:reddit.com "{town}" "{zip_code}" restaurant OR store OR rent OR traffic',
    'site:twitter.com "{town} {state}" business OR opening OR closing OR development',
]

# State to subreddit mapping
STATE_SUBREDDITS = {
    "NJ": "newjersey", "NY": "newyork", "CA": "california", "TX": "texas",
    "FL": "florida", "PA": "pennsylvania", "IL": "illinois", "OH": "ohio",
    "GA": "georgia", "MA": "massachusetts", "VA": "virginia", "WA": "washington",
    "CO": "colorado", "AZ": "arizona", "NC": "northcarolina", "MI": "michigan",
    "MD": "maryland", "CT": "connecticut", "OR": "oregon", "SC": "southcarolina",
}

SOCIAL_PULSE_INSTRUCTION = """You are a local community sentiment analyst. You have access to Google Search.

Execute the provided search queries to find what locals are discussing on Reddit and Twitter/X.

FOCUS ON (last 30 days only):
- Community complaints or excitement about the area
- Opinions on new businesses opening or closing
- Rent / real estate sentiment
- Traffic or parking complaints
- Any local controversy or drama affecting businesses

IGNORE:
- Anything older than 30 days
- National news not specific to this location
- Generic promotional content
- Individual business reviews
- News articles (those are handled elsewhere)

Return a structured summary with 3-5 bullet points. Each bullet should note:
- What the signal is
- Where you found it (Reddit thread, Twitter, etc.)
- When (approximate date)
- Why it matters for local businesses

If nothing relevant in the last 30 days: "No significant local chatter found for this period." Do NOT make anything up."""


_SocialPulseLlmAgent = LlmAgent(
    name="social_pulse",
    model=AgentModels.PRIMARY_MODEL,
    description="Scans Reddit and Twitter/X for community sentiment about an area.",
    instruction=SOCIAL_PULSE_INSTRUCTION,
    tools=[google_search],
    on_model_error_callback=fallback_on_error,
)

async def _run_social_pulse(town: str, state: str, zip_code: str) -> dict[str, Any]:
    """Run social pulse research. Returns dict with summary text."""
    empty: dict[str, Any] = {"summary": "", "town": town, "queriesUsed": 0}

    if not town or town == zip_code:
        return empty

    try:
        state_sub = STATE_SUBREDDITS.get(state.upper(), state.lower())
        queries = [
            q.format(town=town, state=state, state_sub=state_sub, zip_code=zip_code)
            for q in SOCIAL_PULSE_QUERIES
        ]
        prompt = (
            f"Research community sentiment for {town}, {state} (zip: {zip_code}).\n\n"
            f"Execute these search queries and synthesize findings:\n\n"
            + "\n".join(f"{i+1}. {q}" for i, q in enumerate(queries))
            + f"\n\nCurrent date: {datetime.now().strftime('%Y-%m-%d')}\n\n"
            f"Only report what you actually find. Do not fabricate information."
        )

        result = await run_agent_to_text(
            _SocialPulseLlmAgent, prompt, app_name="social_pulse",
            run_config=RunConfig(max_llm_calls=3),
        )

        if result and len(result) > 20:
            return {
                "summary": result,
                "town": town,
                "state": state,
                "queriesUsed": len(queries),
                "fetchedAt": datetime.utcnow().isoformat(),
            }
        return empty

    except Exception as e:
        logger.error(f"[SocialPulse] Failed for {town}, {state}: {e}")
        return empty


# ---------------------------------------------------------------------------
# CachedSocialPulseAgent — city-level 7d cache
# ---------------------------------------------------------------------------

class CachedSocialPulseAgent(BaseAgent):
    """Social pulse with city-level 7d cache.

    Cache key: "social:{city_slug}"  TTL: TTL_WEEKLY (7 days)
    Output state key: "socialPulse"

    All zips in the same city share one result per week.
    """

    name: str = "SocialPulseResearch"
    description: str = "Community sentiment from Reddit and Twitter/X. Cached 7d per city."

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        from hephae_db.firestore.data_cache import get_cached, set_cached, TTL_WEEKLY

        state = ctx.session.state
        city = state.get("city", "")
        st = state.get("state", "")
        zip_code = state.get("zipCode", "")

        city_slug = city.lower().strip().replace(" ", "-") if city else zip_code

        cached = await get_cached("social", city_slug)
        if cached:
            logger.info(f"[SocialPulse] Cache hit for {city_slug} (7d TTL)")
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                actions=EventActions(state_delta={"socialPulse": cached}),
            )
            return

        logger.info(f"[SocialPulse] Cache miss for {city_slug} — running research")
        result = await _run_social_pulse(city, st, zip_code)

        if result.get("summary"):
            await set_cached("social", city_slug, result, ttl_days=TTL_WEEKLY)

        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            actions=EventActions(state_delta={"socialPulse": result}),
        )


# Backward compat
async def fetch_social_pulse(
    town: str,
    state: str = "",
    zip_code: str = "",
) -> dict[str, Any]:
    return await _run_social_pulse(town, state, zip_code)
