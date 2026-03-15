"""
BatchSupervisorAgent — summarizes a large discovery sweep for the Admin UI.

Analyzes scores across multiple businesses to surface the most 
valuable leads and identify potential data quality issues.
"""

from __future__ import annotations

import logging
from google.adk.agents import LlmAgent
from hephae_api.config import AgentModels
from hephae_common.adk_helpers import run_agent_to_text
from hephae_common.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)

SUPERVISOR_INSTRUCTION = """You are a Senior Business Development Supervisor.
Your job is to provide a "Cliffnotes" summary of a recent business discovery sweep.

You will be given a list of businesses found in a zip code/area, along with their high-level scores (SEO, Margin, Social).

Your summary MUST include:
1. **The Volume**: Total businesses found.
2. **The "Gold" Leads**: Identify the top 3-5 businesses that represent the biggest opportunity (e.g., high revenue potential but low SEO/Margin scores).
3. **Data Quality**: Flag any obvious issues (e.g., "5 businesses have same address", "High rate of missing websites").
4. **Action Recommendation**: One clear next step for the Admin.

Format: Use professional, concise bullet points. Keep it under 150 words."""

BatchSupervisorAgent = LlmAgent(
    name="batch_supervisor",
    model=AgentModels.PRIMARY_MODEL, # Uses Flash for cost efficiency
    instruction=SUPERVISOR_INSTRUCTION,
    on_model_error_callback=fallback_on_error,
)

async def generate_batch_summary(area_name: str, businesses: list[dict]) -> str:
    """Generate a high-level summary of a discovery batch."""
    # Create a condensed data string for the LLM
    condensed = []
    for b in businesses[:100]: # Limit context
        scores = b.get("latestOutputs", {})
        seo = scores.get("seo_auditor", {}).get("score", "N/A")
        margin = scores.get("margin_surgeon", {}).get("score", "N/A")
        condensed.append(f"- {b['name']}: SEO={seo}, Margin={margin}, Zip={b.get('zipCode')}")
    
    prompt = f"AREA: {area_name}\nDATA:\n" + "\n".join(condensed)
    
    summary = await run_agent_to_text(BatchSupervisorAgent, prompt, app_name="batch_supervisor")
    return summary or "Batch sweep complete. Ready for manual review."
