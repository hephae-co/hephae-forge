"""Eval wrapper — re-exports margin_surgery_orchestrator as root_agent for ADK AgentEvaluator.

The margin surgeon pipeline runs:
  VisionIntake → (Benchmarker || CommodityWatchdog) → Surgeon → Advisor
"""

from hephae_capabilities.margin_analyzer.agent import margin_surgery_orchestrator as root_agent

__all__ = ["root_agent"]
