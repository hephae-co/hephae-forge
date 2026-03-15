"""Zip code research agent — uses GOOGLE_SEARCH to gather comprehensive local data."""

from __future__ import annotations

import logging
import re

from google.adk.agents import LlmAgent
from google.adk.tools import google_search

from hephae_api.config import AgentModels
from hephae_common.adk_helpers import run_agent_to_text
from hephae_common.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)

ZipCodeResearchAgent = LlmAgent(
    name="zipcode_researcher",
    model=AgentModels.PRIMARY_MODEL,
    description="Researches a US zip code using Google Search to gather comprehensive local data.",
    instruction="""You are a comprehensive zip code research analyst. Your task is to deeply research a US zip code provided by the user.

Execute thorough Google searches to gather data across these 9 categories:

1. **Geography & Location**: City/town name, county, state, nearby landmarks, climate zone, urban/suburban/rural classification. IMPORTANT: Also identify the DMA (Designated Market Area) region name for this zip code (e.g., "New York NY", "Los Angeles CA"). State it clearly as "DMA Region: <name>".

2. **Demographics**: Population size, age distribution, median household income, education levels, racial/ethnic composition.

3. **Census & Housing**: Number of households, homeownership rate, median home value, median rent, housing growth trends.

4. **Local Business Landscape**: Major employers, dominant business categories, number of active businesses, notable chains vs. independent shops.

5. **Economic Indicators**: Unemployment rate, job growth sectors, cost of living index, commercial vacancy rates.

6. **Consumer Behavior & Market Gaps**: Spending patterns, underserved business categories, opportunities for new businesses.

7. **Infrastructure & Amenities**: Schools, hospitals, transit options, parks, walkability score.

8. **Upcoming Events & Foot Traffic Drivers**: Search for events happening WITHIN or immediately adjacent to this zip code in the NEXT 2 WEEKS only. Focus on hyper-local events: street fairs, farmers markets, grand openings, local sports games, school events, community gatherings, parades, holiday events, construction/road closures. For each event, note:
   - Exact location (venue name and distance from zip code center if possible)
   - Date and time
   - Expected attendance or scale (small/medium/large)
   - Relevance categories: < 0.5 miles = HIGH impact, 0.5-1.5 miles = MODERATE impact, > 1.5 miles = LOW impact (skip unless city-wide)
   Do NOT include generic statewide or regional events unless they physically occur within this zip code. Do NOT include events more than 2 weeks out.

9. **Weather & Seasonal Patterns**: Get the CURRENT 7-day weather forecast for this specific zip code. Include daily high/low temps, precipitation chances, and any severe weather alerts. Then note how current weather conditions affect local foot traffic and consumer behavior.

For each category, run 1-2 targeted searches. Cite specific data points and statistics whenever possible.
Compile all findings into a structured research document organized by category.""",
    tools=[google_search],
    on_model_error_callback=fallback_on_error,
)


def _extract_dma_name(text: str) -> str:
    """Extract DMA region name from research findings text."""
    patterns = [
        r"DMA\s*(?:Region|Name|Area)?\s*:\s*([^\n,.]+)",
        r"Designated\s+Market\s+Area\s*:\s*([^\n,.]+)",
        r"DMA\s*[-:]\s*([^\n,.]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return re.sub(r"[*#_`]", "", match.group(1)).strip()
    return ""


async def research_zipcode_data(zip_code: str) -> dict[str, str]:
    """Run the GOOGLE_SEARCH-based research agent for a zip code.

    Returns: {"findings": str, "dmaName": str}
    """
    findings = await run_agent_to_text(
        ZipCodeResearchAgent,
        f"Research zip code {zip_code}",
        app_name="zipcode_research",
    )

    dma_name = _extract_dma_name(findings)
    logger.info(f'[ZipCodeResearch] Complete for {zip_code}, DMA: "{dma_name}", findings length: {len(findings)}')

    return {"findings": findings, "dmaName": dma_name}
