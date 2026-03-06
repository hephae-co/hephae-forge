"""County to zip code resolver — ADK agent that maps county names to zip codes."""

from __future__ import annotations

import logging
import re

from google.adk.agents import LlmAgent

from backend.config import AgentModels
from backend.lib.adk_helpers import run_agent_to_json
from backend.lib.model_fallback import fallback_on_error
from backend.types import CountyResolverOutput

logger = logging.getLogger(__name__)

CountyResolverAgent = LlmAgent(
    name="CountyResolver",
    model=AgentModels.PRIMARY_MODEL,
    instruction="""You are a US geography expert. Given a county description (e.g. "Essex County NJ"), return the most populated zip codes in that county.

Return ONLY a valid JSON object with these fields:
- "zipCodes": array of 5-digit zip code strings (e.g. ["07102", "07104", "07110"])
- "countyName": the canonical county name (e.g. "Essex County")
- "state": the two-letter state abbreviation (e.g. "NJ")

Rules:
- Return between 5 and 10 zip codes, ordered by population (most populated first)
- All zip codes must be valid 5-digit US zip codes that actually belong to the specified county
- If the county description is ambiguous or invalid, return an empty zipCodes array and set an "error" field explaining the issue

Example output:
{
  "zipCodes": ["07102", "07104", "07110", "07111", "07112"],
  "countyName": "Essex County",
  "state": "NJ"
}""",
    on_model_error_callback=fallback_on_error,
)


async def resolve_county_zip_codes(
    county: str, max_zip_codes: int = 10
) -> CountyResolverOutput:
    """Resolve a county description to zip codes."""
    logger.info(f"[CountyResolver] Resolving zip codes for: {county} (max: {max_zip_codes})")

    prompt = (
        f'Resolve the zip codes for "{county}". Return at most {max_zip_codes} zip codes.'
        if max_zip_codes != 10
        else f'Resolve the zip codes for "{county}".'
    )

    data = await run_agent_to_json(CountyResolverAgent, prompt, app_name="HephaeAdmin")

    if not data or not isinstance(data, dict):
        return CountyResolverOutput(zipCodes=[], countyName=county, state="", error="Failed to parse agent output")

    # Validate zip codes are 5-digit strings
    raw_zips = data.get("zipCodes", [])
    valid_zips = [z for z in raw_zips if isinstance(z, str) and re.match(r"^\d{5}$", z)][:max_zip_codes]

    result = CountyResolverOutput(
        zipCodes=valid_zips,
        countyName=data.get("countyName", county),
        state=data.get("state", ""),
        error=data.get("error"),
    )

    logger.info(f"[CountyResolver] Resolved {len(result.zipCodes)} zip codes for {result.countyName}, {result.state}")
    return result
