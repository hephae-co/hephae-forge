"""Eval wrapper — wraps competitor_profiler_agent + market_positioning_agent in a
SequentialAgent for ADK AgentEvaluator.

The competitive analysis pipeline runs two LlmAgents sequentially:
  1. CompetitorProfilerAgent: finds and profiles nearby competitors via Google Search
  2. MarketPositioningAgent: synthesizes positioning strategy from profiler output
"""

from google.adk.agents import SequentialAgent

from hephae_capabilities.competitive_analysis.agent import (
    competitor_profiler_agent,
    market_positioning_agent,
)

root_agent = SequentialAgent(
    name="CompetitiveAnalysisPipeline",
    description="Full competitive analysis: profile competitors then synthesize market positioning.",
    sub_agents=[competitor_profiler_agent, market_positioning_agent],
)

__all__ = ["root_agent"]
