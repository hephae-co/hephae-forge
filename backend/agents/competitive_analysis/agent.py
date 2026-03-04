"""
Competitive Analysis agents — CompetitorProfiler + MarketPositioning.
Port of src/agents/competitive-analysis/analyzer.ts.
"""

from google.adk.agents import LlmAgent

from backend.config import AgentModels, ThinkingPresets
from backend.lib.model_fallback import fallback_on_error
from backend.agents.shared_tools import google_search_tool
from backend.agents.competitive_analysis.prompts import (
    COMPETITOR_PROFILER_INSTRUCTION,
    MARKET_POSITIONING_INSTRUCTION,
)

competitor_profiler_agent = LlmAgent(
    name="CompetitorProfilerAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=COMPETITOR_PROFILER_INSTRUCTION,
    tools=[google_search_tool],
    on_model_error_callback=fallback_on_error,
)

market_positioning_agent = LlmAgent(
    name="MarketPositioningAgent",
    model=AgentModels.PRIMARY_MODEL,
    generate_content_config=ThinkingPresets.HIGH,
    instruction=MARKET_POSITIONING_INSTRUCTION,
    on_model_error_callback=fallback_on_error,
)
