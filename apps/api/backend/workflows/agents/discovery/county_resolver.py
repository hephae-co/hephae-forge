"""County to zip code resolver — ADK agent that maps county names to zip codes."""

from __future__ import annotations

import logging
import re

from google.adk.agents import LlmAgent

from backend.config import AgentModels
from hephae_common.adk_helpers import run_agent_to_json
from hephae_db.schemas import CountyResolverOutput
from hephae_common.model_fallback import fallback_on_error

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

    result = await run_agent_to_json(
        CountyResolverAgent, prompt, app_name="HephaeAdmin", response_schema=CountyResolverOutput
    )

    if not result or not isinstance(result, CountyResolverOutput):
        return CountyResolverOutput(zipCodes=[], countyName=county, state="", error="Failed to parse agent output")

    # Validate zip codes are 5-digit strings
    valid_zips = [z for z in result.zipCodes if isinstance(z, str) and re.match(r"^\d{5}$", z)][:max_zip_codes]

    validated_result = CountyResolverOutput(
        zipCodes=valid_zips,
        countyName=result.countyName or county,
        state=result.state or "",
        error=result.error,
    )

    logger.info(f"[CountyResolver] Resolved {len(validated_result.zipCodes)} zip codes for {validated_result.countyName}, {validated_result.state}")
    return validated_result
