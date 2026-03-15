"""Industry analyst agent — deep sector analysis."""

from __future__ import annotations

import logging

from google.adk.agents import LlmAgent

from hephae_api.config import AgentModels, ThinkingPresets
from hephae_common.adk_helpers import run_agent_to_json
from hephae_db.schemas import IndustryAnalystOutput
from hephae_common.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)

IndustryAnalystAgent = LlmAgent(
    name="industry_analyst",
    model=AgentModels.PRIMARY_MODEL,
    generate_content_config=ThinkingPresets.DEEP,
    description="Performs deep industry/sector analysis to understand challenges, opportunities, trends, and benchmarks.",
    instruction="""You are a senior industry analyst. Analyze the given SECTOR for small businesses.

Return JSON with: overview (2 sentences), marketSize, growthRate, challenges (top 5), opportunities (top 5), trends (5-7), consumerBehavior, technologyAdoption, regulatoryEnvironment (2 sentences), benchmarks.

Keep ALL description/impact fields to ONE sentence max. Use specific numbers.

Schema:
{
  "overview": "2 sentences max",
  "marketSize": "$XB", "growthRate": "X%",
  "challenges": [{ "title": "short", "description": "1 sentence", "severity": "low|medium|high" }],
  "opportunities": [{ "title": "short", "description": "1 sentence", "timeframe": "immediate|short_term|long_term" }],
  "trends": [{ "name": "short", "direction": "rising|stable|declining", "description": "1 sentence" }],
  "consumerBehavior": [{ "shift": "phrase", "impact": "1 sentence" }],
  "technologyAdoption": [{ "technology": "name", "adoptionLevel": "early|growing|mainstream", "relevance": "1 sentence" }],
  "regulatoryEnvironment": "2 sentences",
  "benchmarks": { "gross_margin_pct": num, "net_margin_pct": num, "avg_ticket_size": num, "labor_cost_pct": num, "rent_pct_revenue": num, "failure_rate_1yr": num, "failure_rate_5yr": num, "avg_startup_cost": num }
}

Return ONLY valid JSON.""",
    on_model_error_callback=fallback_on_error,
)


async def analyze_industry(sector: str) -> dict:
    """Analyze an industry sector and return structured analysis."""
    result = await run_agent_to_json(
        IndustryAnalystAgent,
        f"SECTOR: {sector}",
        app_name="industry_analyst",
        response_schema=IndustryAnalystOutput,
    )
    if not result or not isinstance(result, IndustryAnalystOutput):
        raise ValueError(f"Failed to analyze industry '{sector}' — agent returned invalid output")
    return result.model_dump()
