"""Social Pulse — community sentiment via Gemini Google Search grounding.

Uses Gemini's built-in google_search tool with site:-targeted queries against
Reddit, X, Patch, TapInto to synthesize what locals are discussing about an area.

No external APIs needed — piggybacks on ADK's Google Search grounding.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.tools import google_search

from hephae_api.config import AgentModels
from google.adk.runners import RunConfig
from hephae_common.adk_helpers import run_agent_to_text
from hephae_common.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)

SOCIAL_PULSE_QUERIES = [
    'site:reddit.com/r/{state_sub} "{town}" new business OR closing OR opening OR construction OR development',
    'site:reddit.com "{town}" "{zip_code}" restaurant OR store OR rent OR traffic',
    'site:twitter.com "{town} {state}" business OR opening OR closing OR development',
    'site:patch.com "{town}" business OR development OR permit OR budget',
    'site:tapinto.net "{town}" business OR development OR council',
]

# State to subreddit mapping (common ones)
STATE_SUBREDDITS = {
    "NJ": "newjersey", "NY": "newyork", "CA": "california", "TX": "texas",
    "FL": "florida", "PA": "pennsylvania", "IL": "illinois", "OH": "ohio",
    "GA": "georgia", "MA": "massachusetts", "VA": "virginia", "WA": "washington",
    "CO": "colorado", "AZ": "arizona", "NC": "northcarolina", "MI": "michigan",
    "MD": "maryland", "CT": "connecticut", "OR": "oregon", "SC": "southcarolina",
}

SOCIAL_PULSE_INSTRUCTION = """You are a local community sentiment analyst. You have access to Google Search.

Execute the provided search queries to find what locals are discussing about this area on Reddit, Twitter/X, Patch.com, and TapInto.

FOCUS ON (last 30 days only):
- New businesses opening or closing
- Construction / development activity
- Local government decisions affecting businesses
- Community complaints or excitement about the area
- Rent / real estate changes
- Traffic or parking changes
- Events or seasonal patterns

IGNORE:
- Anything older than 30 days
- National news not specific to this location
- Generic promotional content
- Individual business reviews (we have Yelp for that)

Return a structured summary with 3-5 bullet points. Each bullet should note:
- What the signal is
- Where you found it (Reddit, Patch, etc.)
- When (approximate date)
- Why it matters for local businesses

If you find nothing relevant in the last 30 days, say "No significant local chatter found for this period." Do NOT make anything up."""

SocialPulseAgent = LlmAgent(
    name="social_pulse",
    model=AgentModels.PRIMARY_MODEL,
    description="Scans social media and local news for community sentiment about an area.",
    instruction=SOCIAL_PULSE_INSTRUCTION,
    tools=[google_search],
    on_model_error_callback=fallback_on_error,
)


async def fetch_social_pulse(
    town: str,
    state: str = "",
    zip_code: str = "",
) -> dict[str, Any]:
    """Fetch social/community pulse for a location via search grounding.

    Returns dict with summary text and metadata.
    """
    empty: dict[str, Any] = {"summary": "", "town": town, "queriesUsed": 0}

    if not town or town == zip_code:
        # Can't search social media with just a zip code
        return empty

    try:
        state_sub = STATE_SUBREDDITS.get(state.upper(), state.lower())

        # Format queries
        queries = []
        for template in SOCIAL_PULSE_QUERIES:
            q = template.format(
                town=town,
                state=state,
                state_sub=state_sub,
                zip_code=zip_code,
            )
            queries.append(q)

        # Build prompt with all queries for the agent to execute
        prompt = f"""Research community sentiment for {town}, {state} (zip: {zip_code}).

Execute these search queries and synthesize findings:

{chr(10).join(f'{i+1}. {q}' for i, q in enumerate(queries))}

Current date: {datetime.now().strftime('%Y-%m-%d')}

Remember: Only report what you actually find. Do not fabricate information."""

        logger.info(f"[SocialPulse] Searching community sentiment for {town}, {state}")

        result = await run_agent_to_text(
            SocialPulseAgent,
            prompt,
            app_name="social_pulse",
            run_config=RunConfig(max_llm_calls=5),
        )

        if result and len(result) > 20:
            logger.info(f"[SocialPulse] Got {len(result)} chars of community sentiment")
            return {
                "summary": result,
                "town": town,
                "state": state,
                "queriesUsed": len(queries),
                "fetchedAt": datetime.utcnow().isoformat(),
            }
        else:
            logger.info(f"[SocialPulse] No significant social signals for {town}")
            return empty

    except Exception as e:
        logger.error(f"[SocialPulse] Failed for {town}, {state}: {e}")
        return empty
