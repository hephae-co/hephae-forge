"""Eval wrapper — re-exports InsightsAgent as root_agent for ADK AgentEvaluator."""

from backend.workflows.agents.insights.insights_agent import InsightsAgent as root_agent

__all__ = ["root_agent"]
