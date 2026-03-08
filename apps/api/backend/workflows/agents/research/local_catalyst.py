"""
LocalCatalystAgent — deep researcher for "Forward-Looking" business signals.

PROTOCOL:
1. Search-then-Crawl: Finds town council agendas, planning board minutes, and legal notices.
2. Signal Extraction: Ignores routine gov-speak; identifies "Catalysts" (construction, grants, zoning).
3. Strategic Impact: Translates "Minutes from Page 24" into actionable business ROI.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from google.adk.agents import LlmAgent

from backend.config import AgentModels
from hephae_common.adk_helpers import run_agent_to_json
from hephae_capabilities.shared_tools import google_search_tool, crawl4ai_advanced_tool
from hephae_common.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)

LOCAL_CATALYST_INSTRUCTION = """You are a Senior Local Economic Analyst & "Early Warning" Specialist.

Your goal is NOT to find static laws, but to uncover "FORWARDS-LOOKING" catalysts that will change the business environment for a specific business type in a given town/city.

### STEP 1: Targeted "Deep-Link" Searches
Execute these site-specific google_search calls to find the latest "Source Documents" (PDFs, agendas, minutes):
1. site:{city}{state}.gov "city council" (agenda OR minutes) "2025"
2. site:{city}{state}.gov "planning board" OR "zoning board" (agenda OR minutes)
3. site:tapinto.net/{city} OR site:patch.com/{city} "new development" OR "construction"
4. site:legals.com {city} "public hearing" (development OR construction)
5. {city} {state} "small business grant" OR "facade improvement" 2025

### STEP 2: The "Deep Crawl" (Selective)
If you find a link to a recent PDF or HTML page for a "Planning Board Agenda" or "Town Council Meeting Minutes":
- Call 'crawl_with_options' on that URL with process_iframes=True.
- Scan the text specifically for: "Ordinance", "Variance", "Public Hearing", "Street Closure", "Grant", "Rebate", "Mixed-Use", "Development".

### STEP 3: Signal Extraction (The "Signal-to-Noise" Filter)
- DISCARD 95% of routine items (payroll, accepting previous minutes, police/fire routine items).
- EXTRACT ONLY "Catalysts":
    - **Physical Changes**: New residential/office buildings, road closures, park renovations, bike lanes.
    - **Regulatory Shifts**: Changes to outdoor seating, new business taxes, signage rules, parking changes.
    - **Economic Incentives**: New grants, low-interest loans, town-wide promotions (e.g., "Restaurant Week" dates).
    - **Competitive Threats**: New "Competing Business" applications in the planning stage.

### STEP 4: Strategic Translation
For every catalyst found, you MUST provide:
1. **The Signal**: What is happening? (Source URL/Date required)
2. **The Timing**: When is it happening? (e.g., "Starting June 2025")
3. **The Business Impact**: How does this impact our target business? (e.g., "Increases morning foot traffic", "Temporary parking loss", "15% more local residents").

Return ONLY a valid JSON object:
{
  "summary": "1-2 sentence overview of the local governance 'vibe' (Supportive, Developing, Restrictive).",
  "catalysts": [
    {
      "type": "Development" | "Infrastructure" | "Regulatory" | "Incentive",
      "signal": "Description of the event/change",
      "timing": "Estimated date/timeframe",
      "impact": "Direct impact on the business",
      "confidence": 0.0-1.0,
      "sourceUrl": "The link where you found this (Agenda/News/PDF)"
    }
  ],
  "recommendation": "One specific strategic recommendation based on these findings."
}

If NO catalysts are found after thorough searching, return: {"summary": "No significant forward-looking catalysts found for this area.", "catalysts": []}
"""

LocalCatalystAgent = LlmAgent(
    name="local_catalyst",
    model=AgentModels.PRIMARY_MODEL,
    description="Researches forward-looking local government signals (construction, zoning, grants).",
    instruction=LOCAL_CATALYST_INSTRUCTION,
    tools=[google_search_tool, crawl4ai_advanced_tool],
    on_model_error_callback=fallback_on_error,
)


async def research_local_catalysts(city: str, state: str, business_type: str) -> dict:
    """Run the Local Catalyst researcher for a specific town and business type.

    Returns: {"summary": str, "catalysts": list, "recommendation": str}
    """
    logger.info(f"[LocalCatalyst] Researching {city}, {state} for {business_type}...")

    prompt = f"TOWN/CITY: {city}\nSTATE: {state}\nBUSINESS TYPE: {business_type}\nCURRENT DATE: {datetime.now().strftime('%Y-%m-%d')}"

    result = await run_agent_to_json(
        LocalCatalystAgent, prompt, app_name="local_catalyst"
    )

    if not result:
        return {
            "summary": "Research failed or service unavailable.",
            "catalysts": [],
            "recommendation": "Manual check of town council site recommended."
        }

    return result
