"""Local sector trends agent — extracts sector-specific insights from zip code reports."""

from __future__ import annotations

import json
import logging

from google.adk.agents import LlmAgent

from hephae_api.config import AgentModels
from hephae_common.adk_helpers import run_agent_to_json
from hephae_common.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)

LocalSectorTrendsAgent = LlmAgent(
    name="local_sector_trends",
    model=AgentModels.PRIMARY_MODEL,
    description="Extracts sector-specific trends from zip code research reports.",
    instruction="""You are a local market trends analyst. Given a ZIP CODE REPORT and a SECTOR, extract sector-specific insights.

Return a JSON object with:
{
  "zipCode": string,
  "relevantTrends": [
    { "term": string, "direction": "rising"|"declining", "insight": string }
  ],
  "sectorDemandSignals": [string] (3-5 signals from the data),
  "competitorDensity": string (assessment: "low"|"moderate"|"high"|"saturated"),
  "localOpportunities": [string] (3-5 specific opportunities)
}

Focus on data-driven insights specific to this sector in this local market.""",
    on_model_error_callback=fallback_on_error,
)


async def analyze_local_sector_trends(
    zip_code: str,
    sector: str,
    report: dict,
) -> dict:
    """Extract sector-relevant insights from a zip code report."""
    # Condense report to key sections
    sections = report.get("sections", {})
    condensed = {}
    for key, section in sections.items():
        if isinstance(section, dict):
            condensed[key] = {
                "summary": (section.get("content", "") or "")[:300],
                "key_facts": section.get("key_facts", []),
            }

    prompt = f"ZIP CODE: {zip_code}\nSECTOR: {sector}\n\nZIP CODE REPORT:\n{json.dumps(condensed)}"

    result = await run_agent_to_json(LocalSectorTrendsAgent, prompt, app_name="local_sector_trends")

    if result and isinstance(result, dict):
        result["zipCode"] = zip_code
        return result

    return {
        "zipCode": zip_code,
        "relevantTrends": [],
        "sectorDemandSignals": [],
        "competitorDensity": "unknown",
        "localOpportunities": [],
    }
