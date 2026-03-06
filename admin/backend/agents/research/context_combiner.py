"""Context combiner agent — synthesizes multiple zip code reports into unified context."""

from __future__ import annotations

import json
import logging

from google.adk.agents import LlmAgent

from backend.config import AgentModels
from backend.lib.adk_helpers import run_agent_to_json
from backend.lib.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)

ContextCombinerAgent = LlmAgent(
    name="context_combiner",
    model=AgentModels.PRIMARY_MODEL,
    description="Combines multiple zip code research reports into a unified reusable context.",
    instruction="""You are a data synthesis specialist. Combine multiple zip code research reports into a unified market context.

Return a JSON object with:
{
  "summary": string (3-5 sentence overview of the combined market picture),
  "keySignals": [string] (5-8 key market signals across all data),
  "demographicHighlights": [string] (5-8 notable demographic patterns),
  "marketGaps": [string] (3-5 underserved categories or opportunities),
  "trendingTerms": [string] (5-10 notable trending search terms from the area)
}

Be specific — reference zip codes, numbers, and trends. Return ONLY valid JSON.""",
    on_model_error_callback=fallback_on_error,
)


async def combine_research_context(reports: list[dict]) -> dict:
    """Combine multiple zip code reports into a unified context."""
    # Condense reports for token efficiency
    condensed = []
    for report in reports:
        entry = {
            "zip_code": report.get("zip_code", ""),
            "summary": report.get("summary", ""),
        }
        sections = report.get("sections", {})
        for key, section in sections.items():
            if isinstance(section, dict):
                entry[key] = section.get("key_facts", [])
        condensed.append(entry)

    prompt = f"ZIP CODE REPORTS:\n{json.dumps(condensed)}"

    result = await run_agent_to_json(ContextCombinerAgent, prompt, app_name="context_combiner")
    return result or {
        "summary": "",
        "keySignals": [],
        "demographicHighlights": [],
        "marketGaps": [],
        "trendingTerms": [],
    }
