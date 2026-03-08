"""Eval wrapper — re-exports context_gathering_pipeline as root_agent for ADK AgentEvaluator.

The traffic forecaster pipeline has two stages:
  1. ParallelAgent (context_gathering_pipeline): gathers POIs, weather, events via ADK
  2. Synthesis: uses raw genai client (not an ADK agent)

We eval stage 1 — the intelligence gathering portion.
"""

from hephae_capabilities.traffic_forecaster.agent import context_gathering_pipeline as root_agent

__all__ = ["root_agent"]
