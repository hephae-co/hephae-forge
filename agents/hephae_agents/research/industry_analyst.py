"""Industry analyst agent — deep sector analysis."""

from __future__ import annotations

import logging

from google.adk.agents import LlmAgent

from hephae_api.config import AgentModels
from hephae_common.adk_helpers import run_agent_to_json
from hephae_db.schemas import IndustryAnalystOutput
from hephae_common.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)

IndustryAnalystAgent = LlmAgent(
    name="industry_analyst",
    model=AgentModels.ENHANCED_MODEL,
    description="Performs deep industry/sector analysis to understand challenges, opportunities, trends, and benchmarks.",
    instruction="""You are a senior industry analyst with deep expertise across small business sectors.

You will receive a SECTOR name (e.g., "bakeries", "hairdressers", "laundromats", "restaurants").

Perform a comprehensive industry analysis covering:

1. **Overview**: What this sector looks like today — key characteristics, business models, customer segments
2. **Market Size & Growth**: Estimated US market size, annual growth rate, trajectory
3. **Top Challenges**: The 5 most pressing challenges businesses in this sector face RIGHT NOW
4. **Top Opportunities**: The 5 most actionable opportunities for a NEW entrant or existing small business
5. **Industry Trends**: 5-7 key trends with direction (rising/stable/declining)
6. **Consumer Behavior Shifts**: How customer expectations and behaviors are changing
7. **Technology Adoption**: Key technologies and their adoption levels
8. **Regulatory Environment**: Key regulations, compliance requirements, recent changes
9. **Industry Benchmarks**: Key financial and operational metrics (averages)

Output MUST STRICTLY be a JSON object with this schema:
{
  "overview": string,
  "marketSize": string,
  "growthRate": string,
  "challenges": [{ "title": string, "description": string, "severity": "low"|"medium"|"high" }],
  "opportunities": [{ "title": string, "description": string, "timeframe": "immediate"|"short_term"|"long_term" }],
  "trends": [{ "name": string, "direction": "rising"|"stable"|"declining", "description": string }],
  "consumerBehavior": [{ "shift": string, "impact": string }],
  "technologyAdoption": [{ "technology": string, "adoptionLevel": "early"|"growing"|"mainstream", "relevance": string }],
  "regulatoryEnvironment": string,
  "benchmarks": { "gross_margin_pct": ..., "net_margin_pct": ..., "avg_ticket_size": ..., "labor_cost_pct": ..., "rent_pct_revenue": ..., "failure_rate_1yr": ..., "failure_rate_5yr": ..., "avg_startup_cost": ... }
}

Be specific with numbers and data points. Use your knowledge of real industry dynamics.""",
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
