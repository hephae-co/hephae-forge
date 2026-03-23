"""
DemographicExpertAgent — targeted Census/ACS data researcher.

Searches specifically for authoritative demographic data (Census Bureau, ACS,
data.census.gov) rather than relying on generic Google Search results that may
return outdated or incorrect population/income statistics.
"""

from __future__ import annotations

import logging

from google.adk.agents import LlmAgent

from hephae_api.config import AgentModels
from hephae_common.adk_helpers import run_agent_to_json
from hephae_agents.shared_tools import google_search_tool
from hephae_common.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)

DEMOGRAPHIC_EXPERT_INSTRUCTION = """You are a US Census Data Specialist. Your job is to find AUTHORITATIVE, DETERMINISTIC demographic data for a given area.

### SEARCH STRATEGY (execute ALL searches):
1. site:data.census.gov "{area}" — Census Bureau QuickFacts
2. "{area}" "median household income" "population" census 2023 OR 2024
3. "{area}" "age distribution" OR "median age" census ACS
4. "{area}" "housing" "owner-occupied" OR "renter-occupied" census
5. "{area}" "poverty rate" OR "per capita income" census
6. "{zip_codes}" demographics "American Community Survey"

### DATA PRIORITIES (most authoritative first):
- Census Bureau QuickFacts (data.census.gov)
- American Community Survey (ACS) 5-year estimates
- City-Data.com (aggregates Census data)
- State/county data portals

### EXTRACTION RULES:
- ALWAYS cite the source year (e.g., "2023 ACS 5-Year Estimates")
- If multiple sources disagree, prefer the Census Bureau value
- Convert all monetary values to current dollars
- Report percentages to one decimal place

Expected output:
{
  "population": { "total": number, "yearOverYearChange": "+X.X%" or "-X.X%", "source": "Census 2023" },
  "medianHouseholdIncome": { "value": number, "comparedToState": "above"|"below"|"at", "source": "ACS 2023" },
  "medianAge": number,
  "ageDistribution": {
    "under18": "XX.X%",
    "18to34": "XX.X%",
    "35to54": "XX.X%",
    "55plus": "XX.X%"
  },
  "housing": {
    "medianHomeValue": number,
    "ownerOccupied": "XX.X%",
    "renterOccupied": "XX.X%",
    "medianRent": number
  },
  "education": {
    "bachelorsOrHigher": "XX.X%",
    "highSchoolOrHigher": "XX.X%"
  },
  "economicIndicators": {
    "povertyRate": "XX.X%",
    "unemploymentRate": "XX.X%",
    "perCapitaIncome": number
  },
  "dataYear": "2023" or "2024",
  "summary": "2-3 sentence demographic profile of this area"
}

If a specific data point cannot be found, use null for that field. Never fabricate numbers."""

DemographicExpertAgent = LlmAgent(
    name="demographic_expert",
    model=AgentModels.PRIMARY_MODEL,
    description="Researches authoritative Census/ACS demographic data for a geographic area.",
    instruction=DEMOGRAPHIC_EXPERT_INSTRUCTION,
    tools=[google_search_tool],
    on_model_error_callback=fallback_on_error,
)


async def research_demographics(area: str, state: str, zip_codes: list[str]) -> dict:
    """Run the Demographic Expert researcher for a specific area.

    Returns structured Census/ACS demographic data.
    """
    logger.info(f"[DemographicExpert] Researching demographics for {area}, {state}...")

    zip_str = ", ".join(zip_codes[:5]) if zip_codes else ""
    prompt = f"AREA: {area}\nSTATE: {state}\nZIP CODES: {zip_str}"

    result = await run_agent_to_json(
        DemographicExpertAgent, prompt, app_name="demographic_expert"
    )

    if not result:
        return {
            "summary": "Demographic research failed or service unavailable.",
            "dataYear": None,
        }

    return result
