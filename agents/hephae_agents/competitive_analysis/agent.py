"""
Competitive Analysis agents — CompetitorProfiler + MarketPositioning as SequentialAgent.

Pipeline: CompetitorProfiler → MarketPositioning (via session state).
"""

import json

from google.adk.agents import LlmAgent, SequentialAgent

from hephae_common.model_config import AgentModels, ThinkingPresets
from hephae_common.model_fallback import fallback_on_error
from hephae_common.adk_callbacks import log_agent_start, log_agent_complete
from hephae_agents.competitive_analysis.prompts import (
    COMPETITOR_PROFILER_INSTRUCTION,
    MARKET_POSITIONING_INSTRUCTION,
)
from hephae_agents.shared_tools.google_search import google_search as google_search_tool
from hephae_db.schemas.agent_outputs import CompetitiveAnalysisOutput


def _profiler_instruction(ctx):
    """Dynamic instruction — injects competitors + context data from session state."""
    parts = [COMPETITOR_PROFILER_INSTRUCTION]
    competitors = ctx.state.get("competitors", [])
    if competitors:
        parts.append(f"\n\nResearch these competitors: {json.dumps(competitors)}")
    context_data = ctx.state.get("contextData", "")
    if context_data:
        parts.append(f"\n\n{context_data}")
    return "\n".join(parts)


def _positioning_instruction(ctx):
    """Dynamic instruction — reads profiler brief + identity from session state."""
    parts = [MARKET_POSITIONING_INSTRUCTION]
    identity = ctx.state.get("identity", {})
    if identity:
        parts.append(f"\n\nTARGET RESTAURANT: {json.dumps(identity)}")
    brief = ctx.state.get("competitorBrief", "")
    if brief:
        parts.append(f"\n\nCOMPETITORS BRIEF:\n{brief}")
    parts.append("\n\nGenerate the final competitive json report.")
    return "\n".join(parts)


competitor_profiler_agent = LlmAgent(
    name="CompetitorProfilerAgent",
    model=AgentModels.PRIMARY_MODEL,
    description="Researches and profiles named competitors from web search sources.",
    instruction=_profiler_instruction,
    output_key="competitorBrief",
    tools=[google_search_tool],
    # Note: ADK built-in google_search cannot be mixed with custom function tools.
    # load_memory_tool removed — competitor data comes via session state.
    on_model_error_callback=fallback_on_error,
)

market_positioning_agent = LlmAgent(
    name="MarketPositioningAgent",
    model=AgentModels.PRIMARY_MODEL,
    description="Synthesizes competitor profiles into a structured market positioning report.",
    generate_content_config=ThinkingPresets.HIGH,
    instruction=_positioning_instruction,
    output_schema=CompetitiveAnalysisOutput,
    on_model_error_callback=fallback_on_error,
)

competitive_pipeline = SequentialAgent(
    name="CompetitivePipeline",
    description="2-stage competitive analysis: profile competitors → synthesize market positioning.",
    sub_agents=[competitor_profiler_agent, market_positioning_agent],
    before_agent_callback=log_agent_start,
    after_agent_callback=log_agent_complete,
)
