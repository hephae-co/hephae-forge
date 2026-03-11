"""
Competitive Analysis agents — CompetitorProfiler + MarketPositioning.
Port of src/agents/competitive-analysis/analyzer.ts.
"""

from google.adk.agents import LlmAgent
from google.adk.tools.load_memory_tool import load_memory_tool

from hephae_common.model_config import AgentModels, ThinkingPresets
from hephae_common.model_fallback import fallback_on_error
from hephae_capabilities.shared_tools import google_search_tool
from hephae_capabilities.competitive_analysis.prompts import (
    COMPETITOR_PROFILER_INSTRUCTION,
    MARKET_POSITIONING_INSTRUCTION,
)
from hephae_db.schemas.agent_outputs import CompetitiveAnalysisOutput

competitor_profiler_agent = LlmAgent(
    name="CompetitorProfilerAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=COMPETITOR_PROFILER_INSTRUCTION,
    tools=[google_search_tool, load_memory_tool],
    on_model_error_callback=fallback_on_error,
)

market_positioning_agent = LlmAgent(
    name="MarketPositioningAgent",
    model=AgentModels.PRIMARY_MODEL,
    generate_content_config=ThinkingPresets.HIGH,
    instruction=MARKET_POSITIONING_INSTRUCTION,
    output_schema=CompetitiveAnalysisOutput,
    on_model_error_callback=fallback_on_error,
)
