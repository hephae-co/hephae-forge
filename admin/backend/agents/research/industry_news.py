"""Industry news agent — uses GOOGLE_SEARCH for recent industry intelligence."""

from __future__ import annotations

import logging

from google.adk.agents import LlmAgent
from google.adk.tools import google_search

from backend.config import AgentModels
from backend.lib.adk_helpers import run_agent_to_json
from backend.lib.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)

IndustryNewsAgent = LlmAgent(
    name="industry_news",
    model=AgentModels.PRIMARY_MODEL,
    description="Researches recent industry news, commodity prices, and regulatory updates.",
    instruction="""You are an industry intelligence researcher. Given an INDUSTRY and AREA, search for the latest developments.

Research and return a JSON object with:
{
  "recentNews": [
    { "headline": string, "summary": string (2-3 sentences), "relevance": string (why it matters for local businesses), "source": string }
  ] (5-8 items from the last 6 months),
  "priceTrends": [
    { "item": string (e.g., "flour", "coffee beans"), "trend": "rising"|"stable"|"declining", "detail": string }
  ] (4-6 items — key commodity/input prices),
  "regulatoryUpdates": [
    { "title": string, "summary": string, "impact": "low"|"medium"|"high" }
  ] (2-4 items — recent or upcoming regulatory changes)
}

Focus on actionable intelligence that would affect a small business owner's decisions.
Return ONLY valid JSON. No markdown fencing.""",
    tools=[google_search],
    on_model_error_callback=fallback_on_error,
)


async def research_industry_news(industry: str, area: str) -> dict:
    """Research recent industry news for a specific industry in an area."""
    result = await run_agent_to_json(
        IndustryNewsAgent,
        f"INDUSTRY: {industry}\nAREA: {area}",
        app_name="industry_news",
    )
    return result or {"recentNews": [], "priceTrends": [], "regulatoryUpdates": []}
